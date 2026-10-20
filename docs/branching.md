# Конвенції гілок і комітів

## Назви гілок

Кожну зміну виконуємо в окремій гілці, створеній від актуальної `main`.

Формат:

`feature/ім'я-коротка-тема`

Приклади:

- `feature/skrypaalina-branching`
- `feature/mariexssin-readme-template`

Перед створенням гілки оновіть локальну `main`:

```bash
git switch main
git pull
git switch -c feature/ім'я-тема

## Локальний hook для повідомлень комітів

Hook зберігається у .githooks/commit-msg і перевіряє формат першого рядка повідомлення коміту. Дозволені типи: feat, fix, docs, chore, refactor і test. Наприклад: docs: update branching guide.

Після клонування кожен учасник окремо під'єднує hook у своїй копії репозиторію:

Hook перевіряє тільки перший рядок повідомлення коміту — тему коміту. Текст повідомлення, який іде нижче, не перевіряється.
```bash
git config core.hooksPath .githooks
