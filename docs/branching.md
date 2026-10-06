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