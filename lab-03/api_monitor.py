#!/usr/bin/env python3
"""Перевіряє API з JSON-конфігурації, журналює збої та сповіщає через Discord."""

import argparse
import datetime as dt
import errno
import json
import os
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


EXIT_CODES = {
    "dns_error": 10,
    "connection_refused": 11,
    "timeout": 12,
    "certificate_error": 13,
    "unexpected_status": 14,
    "slow_response": 15,
    "network_error": 16,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Перевіряє API за JSON-конфігурацією.",
        epilog=(
            "Приклад: python api_monitor.py "
            "--config lab-03/config/targets.json"
        ),
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Шлях до JSON-файлу зі списком цілей.",
    )
    parser.add_argument(
        "--output",
        default="lab-03/logs/api-monitor.jsonl",
        help="Шлях до журналу JSON Lines.",
    )
    return parser.parse_args()


def positive_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value > 0
    )


def load_config(path: str) -> List[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as config_file:
            data = json.load(config_file)
    except FileNotFoundError as exc:
        raise ValueError("Файл конфігурації не знайдено: {}".format(path)) from exc
    except PermissionError as exc:
        raise ValueError("Немає прав прочитати конфігурацію: {}".format(path)) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Некоректний JSON у рядку {}: {}".format(exc.lineno, exc.msg)
        ) from exc
    except OSError as exc:
        raise ValueError("Не вдалося прочитати конфігурацію: {}".format(exc)) from exc

    targets = data.get("targets") if isinstance(data, dict) else None
    if not isinstance(targets, list) or not targets:
        raise ValueError("У конфігурації має бути непорожній список 'targets'.")

    for index, target in enumerate(targets, start=1):
        label = "ціль {}".format(index)

        if not isinstance(target, dict):
            raise ValueError("{} має бути JSON-об'єктом.".format(label))

        for key in (
            "name",
            "url",
            "expected_status",
            "timeout_seconds",
            "slow_threshold_seconds",
        ):
            if key not in target:
                raise ValueError("{}: немає поля '{}'.".format(label, key))

        if not isinstance(target["name"], str) or not target["name"].strip():
            raise ValueError("{}: 'name' має бути непорожнім рядком.".format(label))

        if not isinstance(target["url"], str):
            raise ValueError("{}: 'url' має бути рядком.".format(label))

        if not target["url"].startswith(("http://", "https://")):
            raise ValueError(
                "{}: URL має починатися з http:// або https://.".format(label)
            )

        status = target["expected_status"]
        if isinstance(status, bool) or not isinstance(status, int) or not 100 <= status <= 599:
            raise ValueError(
                "{}: 'expected_status' має бути цілим числом від 100 до 599.".format(label)
            )

        if not positive_number(target["timeout_seconds"]):
            raise ValueError(
                "{}: 'timeout_seconds' має бути більшим за нуль.".format(label)
            )

        if not positive_number(target["slow_threshold_seconds"]):
            raise ValueError(
                "{}: 'slow_threshold_seconds' має бути більшим за нуль.".format(label)
            )

    return targets


def find_cause(error: BaseException) -> List[BaseException]:
    """Повертає ланцюжок причин, зокрема причину urllib.error.URLError."""
    found: List[BaseException] = []
    pending: List[Any] = [error]
    seen = set()

    while pending:
        current = pending.pop()
        if not isinstance(current, BaseException) or id(current) in seen:
            continue

        seen.add(id(current))
        found.append(current)

        for related in (
            getattr(current, "reason", None),
            getattr(current, "__cause__", None),
            getattr(current, "__context__", None),
        ):
            if isinstance(related, BaseException):
                pending.append(related)

    return found


def classify_network_error(error: BaseException) -> str:
    causes = find_cause(error)

    if any(isinstance(item, ssl.SSLError) for item in causes):
        return "certificate_error"

    if any(isinstance(item, socket.gaierror) for item in causes):
        return "dns_error"

    if any(
        isinstance(item, ConnectionRefusedError)
        or getattr(item, "errno", None) == errno.ECONNREFUSED
        for item in causes
    ):
        return "connection_refused"

    if any(
        isinstance(item, (socket.timeout, TimeoutError))
        for item in causes
    ):
        return "timeout"

    return "network_error"


def request_once(url: str, timeout: float) -> int:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "lab-03-api-monitor/1.0"},
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.getcode()
    except urllib.error.HTTPError as exc:
        try:
            return exc.code
        finally:
            exc.close()


def check_target(target: Dict[str, Any], checked_at: str) -> Dict[str, Any]:
    started = time.monotonic()
    attempts = 0
    actual_status: Optional[int] = None
    failure_type: Optional[str] = None
    error_message: Optional[str] = None

    for attempts in (1, 2):
        try:
            actual_status = request_once(
                target["url"],
                float(target["timeout_seconds"]),
            )
            break
        except (
            urllib.error.URLError,
            socket.timeout,
            TimeoutError,
            ssl.SSLError,
            OSError,
        ) as exc:
            failure_type = classify_network_error(exc)
            error_message = str(exc)

            if attempts == 1:
                continue
            break

    duration_ms = round((time.monotonic() - started) * 1000, 2)

    if failure_type is None:
        if actual_status != target["expected_status"]:
            failure_type = "unexpected_status"
            error_message = "Очікувався HTTP {}, отримано {}.".format(
                target["expected_status"], actual_status
            )
        elif duration_ms > float(target["slow_threshold_seconds"]) * 1000:
            failure_type = "slow_response"
            error_message = "Відповідь перевищила налаштований поріг часу."

    return {
        "checked_at": checked_at,
        "name": target["name"],
        "url": target["url"],
        "status": "healthy" if failure_type is None else "problem",
        "expected_status": target["expected_status"],
        "actual_status": actual_status,
        "response_time_ms": duration_ms,
        "attempts": attempts,
        "failure_type": failure_type,
        "error": error_message,
    }


def append_results(path: str, results: List[Dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("a", encoding="utf-8") as output_file:
        for result in results:
            output_file.write(
                json.dumps(result, ensure_ascii=False) + "\n"
            )


def send_discord_alert(webhook_url: str, result: Dict[str, Any]) -> None:
    message = (
        "API monitor: {name}\n"
        "Тип проблеми: {failure_type}\n"
        "Адреса: {url}\n"
        "HTTP-код: {actual_status}; час: {response_time_ms} мс"
    ).format(**result)

    payload = json.dumps({"content": message}).encode("utf-8")
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers=headers,
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=10) as response:
        if not 200 <= response.getcode() < 300:
            raise OSError(
                "Discord повернув HTTP-код {}.".format(response.getcode())
            )


def main() -> int:
    args = parse_args()

    try:
        targets = load_config(args.config)
    except ValueError as exc:
        print("Помилка конфігурації: {}".format(exc), file=sys.stderr)
        return 2

    checked_at = dt.datetime.now(dt.timezone.utc).isoformat()
    results = [check_target(target, checked_at) for target in targets]

    try:
        append_results(args.output, results)
    except OSError as exc:
        print("Не вдалося записати журнал: {}".format(exc), file=sys.stderr)
        return 3

    for result in results:
        if result["status"] == "healthy":
            print(
                "OK: {} — HTTP {}, {} мс".format(
                    result["name"],
                    result["actual_status"],
                    result["response_time_ms"],
                )
            )
        else:
            print(
                "ПРОБЛЕМА: {} — {}".format(
                    result["name"],
                    result["failure_type"],
                )
            )

    problems = [item for item in results if item["status"] == "problem"]
    if not problems:
        print("Усі цілі здорові. Журнал: {}".format(args.output))
        return 0

    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print(
            "Є проблемні цілі, але змінну DISCORD_WEBHOOK_URL не задано.",
            file=sys.stderr,
        )
        return 4

    notification_failed = False
    for result in problems:
        try:
            send_discord_alert(webhook_url, result)
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            notification_failed = True
            print(
                "Не вдалося надіслати сповіщення для {}: {}".format(
                    result["name"], exc
                ),
                file=sys.stderr,
            )

    print("Результати записано в {}".format(args.output))

    if notification_failed:
        return 4

    return EXIT_CODES.get(problems[0]["failure_type"], 16)


if __name__ == "__main__":
    sys.exit(main())