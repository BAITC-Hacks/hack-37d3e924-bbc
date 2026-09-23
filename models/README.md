# Проверенные веса в GitHub Releases

Комплект [models-mac-v1](https://github.com/BAITC-Hacks/hack-37d3e924-bbc/releases/tag/models-mac-v1)
содержит точные веса рабочего Mac-профиля: mixed-STT, Sherpa ONNX
диаризацию и MLX Qwen3-4B-Instruct-2507 4-bit. SHA-256 совпадают с
`ai/mac-models.lock.json` и `prototypes/meeting-mvp/models.lock.json`.
Оригинальные ссылки Hugging Face для этой загрузки не нужны.

## Скачать из клона проекта

Нужны Python 3.10+ и [GitHub CLI](https://cli.github.com/).
Репозиторий закрытый: войдите аккаунтом с правом чтения репозитория.

```bash
gh auth login
python3 scripts/download_models.py --directory .local/models
make up PROFILE=mac MODELS="$PWD/.local/models"
```

Перед первым запуском приложения выполните `make setup PROFILE=mac`, как
в основном README. Загрузка весов занимает около 3.08 ГБ трафика;
подготовьте не менее 6 ГБ свободного диска. Установленная папка занимает
около 3.08 ГБ. Самый большой файл разделён на три части, загрузчик
собирает их автоматически и проверяет SHA-256 каждой части и целого файла.

Повтор той же команды пропускает готовые файлы и использует полностью
скачанные проверенные части. При сетевом сбое загрузчик делает до трёх попыток;
прерванная часть скачивается заново.
Повреждённые данные не заменяют установленную модель. Для проверки без сети:

```bash
python3 scripts/download_models.py --directory .local/models --verify-only
```

Если GitHub CLI повторяет `PROTOCOL_ERROR` или `connection reset by peer`
на больших файлах, повторите загрузку с HTTP/1.1 (это помогло в сети,
где проверялся релиз):

```bash
GODEBUG=http2client=0 python3 scripts/download_models.py --directory .local/models
```

В PowerShell: `$env:GODEBUG = 'http2client=0'`, затем та же команда через `py`.
Это настройка сетевого транспорта GitHub CLI; контрольные суммы по-прежнему
проверяются для всех файлов.

Можно загрузить только нужные компоненты; лицензии сохраняются всегда:

```bash
python3 scripts/download_models.py --directory .local/models --component asr --component diarization
```

На Windows используйте `py` вместо `python3`. ASR и ONNX доступны отдельно;
MLX LLM требует Apple Silicon/macOS. Этот релиз не является комплектом CUDA
и не добавляет поддержку MLX на Windows или обычном Linux.

Для старого Streamlit-прототипа после загрузки также создайте его отметку
проверки (команды из корня проекта, macOS/Linux):

```bash
MEETING_MODEL_DIR="$PWD/.local/models" python3 prototypes/meeting-mvp/download_models.py --verify-only
MEETING_MODEL_DIR="$PWD/.local/models" make prototype
```

При загрузке только двух компонентов передайте те же `--component` команде
проверки прототипа. Его исходные команды копирования и загрузки сохранены.

## Скачать без новой версии исходного кода

Загрузчик и его закреплённый манифест также приложены к релизу:

```bash
gh auth login
gh release download models-mac-v1 --repo BAITC-Hacks/hack-37d3e924-bbc --pattern download_models.py --pattern github-release.lock.json --dir model-setup
python3 model-setup/download_models.py --directory models
```

В автоматизации GitHub CLI может использовать `GH_TOKEN` с доступом на чтение
содержимого репозитория. Передавайте его через секреты окружения, не через URL
или файлы проекта. Доступ к релизу наследуется от закрытого репозитория.

## Происхождение и хранение

В `github-release.lock.json` закреплены исходные URL, размеры, SHA-256
файлов, имена и SHA-256 частей релиза. [NOTICE.md](NOTICE.md) и
[licenses/](licenses/) сохраняют лицензии и атрибуцию. Загрузчик помещает их
в `models/licenses/`; сохраняйте их при переносе весов.

Тяжёлые файлы хранятся в Releases и не входят в историю Git. Скачанный
каталог `.local/models` исключён из Git. GitHub хранит и раздаёт веса;
сама обработка выполняется на компьютере, где запущено приложение.

Проверки загрузчика входят в `make verify`; отдельно:
`python3 -m pytest scripts/tests -q`.
