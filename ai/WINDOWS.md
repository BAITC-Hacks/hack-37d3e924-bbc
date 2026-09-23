# Оригинальный комплект на Windows

Профиль `windows` использует `ai.pipeline.run_pipeline` и общий JSON-контракт. Один отдельный worker последовательно запускает подготовку аудио, TorchScript ASR, Sherpa ONNX и извлечение поручений. Облачных запросов или перехода к фикстуре при ошибке нет.

## Модели и движок

Состав не меняется: `ai/mac-models.lock.json` фиксирует исходный mixed-STT, две ONNX-модели и MLX Qwen3-4B-Instruct-2507-4bit. Доставка: [models/README.md](../models/README.md). Для проверки исходных байтов:

```powershell
python scripts/manage.py doctor --profile windows --device cuda --models .local/models
```

`ai/mlx_torch.py` — собственный адаптер формата, а не официальный Windows-порт MLX. Он сохраняет упакованные 4-битные веса, масштабы и смещения. Для вычисления распаковывается не более 1024 строк матрицы; таблица токенов и выходной слой используют одни буферы. Никакая новая модель или копия полных BF16-весов на диск не создаётся.

Правило исходного формата: младшая тетрада первой, группы по 64 значения, `weight = code * scale + bias`. Выражение вычисляется в FP32 и округляется в BF16. Источники: [формат MLX](https://ml-explore.github.io/mlx/build/html/python/_autosummary/mlx.core.quantize.html), [деквантизация](https://ml-explore.github.io/mlx/build/html/python/_autosummary/mlx.core.dequantize.html), [MLX Qwen3](https://github.com/ml-explore/mlx-lm/blob/v0.31.3/mlx_lm/models/qwen3.py), [Transformers Qwen3](https://github.com/huggingface/transformers/blob/v5.17.0/src/transformers/models/qwen3/modeling_qwen3.py). Другие форматы и архитектуры адаптер отклоняет.

Совпадение исходных весов не гарантирует побитового совпадения генерации разных движков. Tiny-тесты проверяют математическое представление и загрузку; качество на совещаниях требует отдельной оценки.

## Установка и запуск

```powershell
python scripts/manage.py setup --profile windows
# Необязательно для CPU; для проверенного NVIDIA-профиля:
.\prototypes\meeting-mvp\.venv\Scripts\python.exe -m pip install torch==2.14.0+cu130 --index-url https://download.pytorch.org/whl/cu130
.\start-windows.cmd
```

Скрипт использует корневое `.venv`, если оно существует, иначе окружение прототипа. Команду установки CUDA выполняйте в выбранном окружении. Пакеты закреплены в `requirements-windows.lock.txt`; `torch==2.14.0` также допускает установленную сборку `2.14.0+cu130` и не заменяет её при обычной повторной установке.

Явный запуск:

```powershell
.\prototypes\meeting-mvp\.venv\Scripts\python.exe scripts/manage.py run --profile windows --device cuda --models .local/models
# Без совместимой NVIDIA GPU:
.\start-windows.cmd -Device cpu
```

Порт — 8000, только loopback. Ctrl+C останавливает API и worker. Старый Streamlit использует тот же адаптер через `MEETING_LLM_RUNTIME=mlx_torch`; `MEETING_DEVICE` выбирает CPU/CUDA, `MEETING_MODEL_DIR` — подготовленный комплект. Для прототипа нужна отдельная квитанция проверки, которую создаёт явная команда:

```powershell
$env:MEETING_MODEL_DIR = (Resolve-Path .local/models).Path
.\prototypes\meeting-mvp\.venv\Scripts\python.exe prototypes/meeting-mvp/download_models.py --verify-only
$env:MEETING_DEVICE = 'cuda'
.\prototypes\meeting-mvp\start.cmd
```

## Память, контекст, приватность

Начальные лимиты Windows: контекст 2048 токена, ответ 512. Полный BF16-вариант только весов занял бы около 7.49 GiB, поэтому он не создаётся. Полный исходный комплект занимает около 3.08 GB диска. CPU-выполнение поддерживается кодом, но скорость и доступная память зависят от машины.

Этапы запускаются отдельно и освобождают память после завершения. Windows RSS снимается через API ОС, CUDA-пик — счётчиком PyTorch. Размер контекста или запись сверх лимита дают ошибку; содержимое не обрезается незаметно.

Загрузка зависимостей/весов — отдельный подготовительный этап. Inference включает offline-флаги и существующий запрет Python-сокетов. Это не заменяет сетевую изоляцию на уровне ОС для проверки закрытого контура. Живые записи и тексты в облачные API не отправляются.

## Проверка

```powershell
python scripts/manage.py verify --profile fixture
python scripts/manage.py doctor --profile windows --device cuda
```

Модульные тесты адаптера используют маленькие искусственные матрицы и миниатюрный случайный Qwen для проверки интерфейса. Эти тесты не являются результатами распознавания речи.

23.09.2026 выполнен настоящий конвейер на Windows с исходными весами: RTX 3050 Laptop 4 GB, RAM 16 GB, Python 3.14.6, PyTorch 2.14.0+cu130. Вход — специально созданная русская запись System.Speech с двумя голосами, 20.795 секунды; это синтетическое аудио, а не JSON-фикстура. Все 16 файлов моделей проверены по SHA-256.

| Этап | Время |
|---|---:|
| Подготовка аудио | 0.391 с |
| ASR | 4.509 с |
| Диаризация | 3.027 с |
| Поручения и саммари | 185.650 с |
| Весь конвейер | 196.970 с |

Получено 6 реплик, 2 метки говорящих и 2 поручения с правильными известными исполнителями. Пик выделенной CUDA-памяти PyTorch — 2.443 GiB; пиковый RSS LLM-процесса — 2.849 GiB. Это разные показатели; счётчик PyTorch не охватывает все выделения ONNX и драйвера.

Отдельно та же запись загружена через HTTP в приложение, обработана настоящим worker и открыта в браузере. В интерфейсе исправлены саммари и срок, назначены имена говорящим и сохранена версия 2. После остановки и повторного запуска `start-windows.cmd` правки сохранились, исходный результат не изменился. DOCX прочитан через python-docx и проверен на исправления и казахские буквы; визуальная вёрстка Word в этом прогоне не проверялась.

Ограничения прогона: модель пропустила относительный срок «к завтрашнему дню», а саммари неверно связало реплику о неопределённом сроке с отчётом. Нужна ручная проверка; это не оценка качества казахской и смешанной речи или длинных записей. CPU-путь проверен модульно, полный исходный комплект на CPU не замерялся. 240 автоматических тестов и TypeScript/Vite build прошли. Машиночитаемые замеры: [evidence/windows-original-models.json](evidence/windows-original-models.json).
