# Модели уже в репозитории

В этом каталоге находятся **все исходные веса для профилей Mac и Windows**:

- [asr/](asr/): распознавание русской, казахской и смешанной речи;
- [diarization/](diarization/): разделение по голосам;
- [llm/](llm/): MLX Qwen3-4B-Instruct-2507 4-bit для поручений и саммари.

Это обычные файлы Git. Большие веса разбиты на части до 48 МиБ,
чтобы каждый файл укладывался в ограничения GitHub. Git LFS не требуется.

## Для остальных участников

Скачайте репозиторий обычным Git или обновите существующую копию:

```bash
git clone https://github.com/BAITC-Hacks/hack-37d3e924-bbc.git
cd hack-37d3e924-bbc
python3 scripts/prepare_repo_models.py
```

Для существующего клона: `git pull`, затем та же команда сборки.
На Windows вместо `python3` используйте `py` или `python`.
Нужен Python 3.10+; дополнительная библиотека или вход в GitHub CLI не нужны.
Доступ к закрытому репозиторию требуется только на этапе `git clone` / `git pull`.

Команда работает **без сети**: проверяет SHA-256 каждой части,
собирает `asr/model.pt` и `llm/model.safetensors` и проверяет их целиком.
Готовые исправные файлы повторно не собираются; повреждённая часть вызывает
ошибку и не заменяет существующую модель. Исходные части остаются в каталоге.

Скачивание весов — около 3.08 ГБ. Для Git-объектов, частей, собранных моделей
и временных файлов подготовьте **12 ГБ свободного места**. Сборка добавляет
около 3 ГБ к рабочей папке; собранные копии исключены из Git.

Проверить всё без пересборки:

```bash
python3 scripts/prepare_repo_models.py --verify-only
```

Подготовить отдельные компоненты, например для Windows:

```bash
python3 scripts/prepare_repo_models.py --component asr --component diarization
```

## Запуск приложения

На Mac Apple Silicon из корня репозитория:

```bash
make setup PROFILE=mac
make up PROFILE=mac
```

Запуск по умолчанию сам собирает и проверяет `models/`. При необходимости
другой каталог можно задать `MODELS=/absolute/path/to/models`.
Для ручной подготовки также доступно `make models`.

На Mac используется MLX. Windows-профиль `windows` использует те же файлы
через адаптер PyTorch `mlx_torch`; после установки зависимостей запускайте
`start-windows.cmd`. Он также автоматически собирает и проверяет `models/`.
Установка CUDA и ограничения Windows описаны в [ai/WINDOWS.md](../ai/WINDOWS.md).
Эти веса не заменяют отдельный Linux/CUDA-комплект Qwen14B/Community-1.

Для старого Streamlit-прототипа нужна его отметка проверки. macOS/Linux:

```bash
MEETING_MODEL_DIR="$PWD/models" python3 prototypes/meeting-mvp/download_models.py --verify-only
MEETING_MODEL_DIR="$PWD/models" make prototype
```

Windows PowerShell, если подготовлены только ASR и диаризация:

```powershell
$env:MEETING_MODEL_DIR = (Resolve-Path models).Path
py prototypes/meeting-mvp/download_models.py --verify-only --component asr --component diarization
```

## Происхождение и резервная загрузка

`repository-models.lock.json` содержит пути, размеры и SHA-256 исходных файлов
и частей. Они восстанавливают в точности веса из `ai/mac-models.lock.json`
и `prototypes/meeting-mvp/models.lock.json`. [NOTICE.md](NOTICE.md) и
[licenses/](licenses/) сохраняют лицензии и атрибуцию; сохраняйте их при переносе.

Резервная копия остаётся в [GitHub Releases](https://github.com/BAITC-Hacks/hack-37d3e924-bbc/releases/tag/models-mac-v1).
Её можно отдельно скачать через GitHub CLI в `.local/models`:

```bash
gh auth login
python3 scripts/download_models.py --directory .local/models
```

Этот резервный способ не требует скачивать части из дерева Git.
Сборку файлов репозитория и установку из Releases проверяют тесты:
`python3 -m pytest scripts/tests -q`.
