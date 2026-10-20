# Конфлікт у `.editorconfig`

Аліна й Марія незалежно створили `.editorconfig`. Для Bash їхні значення `indent_size` відрізнялися: одна гілка задала `2`, інша — `4`.

## Помилкове вирішення

Помилково залишити обидві версії секції:

```ini
[*.{sh,bash}]
indent_style = space
indent_size = 2

[*.{sh,bash}]
indent_style = space
indent_size = 4
