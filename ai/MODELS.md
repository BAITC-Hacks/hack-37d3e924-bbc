# Выбор и доступ к моделям

Проверено 23.09.2026. Revision закреплены в `models.json`; скачивание отдельно от inference. Оценка качества на наших клипах находится в `EVIDENCE.md` и не заменяется цифрами автора модели.

| Кандидат | Лицензия/доступ | Подключение и роль |
|---|---|---|
| [OpenAI Whisper large-v3](https://huggingface.co/openai/whisper-large-v3) | Apache-2.0 в метаданных HF; исходный Whisper — MIT. Сохранять приложенные лицензии. Ungated. | Базовый кандидат качества; локальная конверсия CT2. На доступном Mac в этом проходе не измерен. |
| [OpenAI Whisper large-v3-turbo](https://huggingface.co/openai/whisper-large-v3-turbo) | MIT, ungated | Мультиязычный кандидат с меньшим декодером; проверяется как основной быстрый ASR. |
| [Shyngys Kazakh Whisper Turbo](https://huggingface.co/shyngys879/kazakh-whisper-large-v3-turbo) | Apache-2.0, ungated | Полный Transformers checkpoint, конвертируется в CT2. Казахский специалист; автор прямо указывает смешанную речь среди ограничений. Нужен отдельный mixed-тест. |
| [Alibi Kazakh/Russian mixed-STT](https://huggingface.co/alibiserikbay/kazakh-russian-mixed-stt) | Apache-2.0, ungated | TorchScript CTC, модель `asr/rukk`, 16 kHz mono, greedy decoding. Отличается от авторского варианта с KenLM: результаты нельзя напрямую приравнивать. |
| [pyannote Community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) | CC-BY-4.0; gated: условия + HF access token для подготовки | Локальная диаризация; используем exclusive tracks для привязки слов и обычные tracks для предупреждения о перекрытии. Не устанавливает личность. |
| [Qwen3-14B](https://huggingface.co/Qwen/Qwen3-14B) | Apache-2.0, ungated | Локальная Transformers-модель. Thinking выключен; задачи/саммари JSON. BF16 или явно выбранный NF4; исходные веса одни. CUDA-кандидат ещё не измерен. |

Совместимость проверена по официальным инструкциям, пакеты серверной конфигурации разрешены в `requirements-cuda.lock.txt`, но их исполнение на GPU пока не проверено:

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper): CUDA 12 + cuDNN 9; finetuned Whisper поддерживается после конверсии. Runtime получает только локальный путь и локальный tokenizer.
- [TorchCodec compatibility](https://github.com/pytorch/torchcodec/tree/v0.8.1): TorchCodec 0.8 ↔ Torch 2.9. Устанавливать TorchAudio той же версии, shared FFmpeg необходим pyannote.
- [Qwen model card](https://huggingface.co/Qwen/Qwen3-14B): Transformers >=4.51; серверный pin 4.57.1 поддерживает Qwen3. Контекст здесь ограничен 8192, не рекламным максимумом модели. Жадное декодирование используется только при `enable_thinking=False`.

Локальная тестовая альтернатива на Apple Silicon: [Sherpa ONNX](https://k2-fsa.github.io/sherpa/onnx/speaker-diarization/models.html), pyannote-segmentation-3.0 ONNX + [3D-Speaker](https://github.com/modelscope/3D-Speaker) embedding, [MLX Qwen3-4B-Instruct-2507 4-bit](https://huggingface.co/mlx-community/Qwen3-4B-Instruct-2507-4bit). Это самостоятельный явный профиль, а не Community-1 или Qwen14B под другим названием. Происхождение/хеши каждого файла — `mac-models.lock.json`. Лицензии проекта Sherpa — Apache-2.0, segmentation export включает MIT/CNRS, 3D-Speaker — Apache-2.0, Qwen — Apache-2.0. При переносе весов сохранять файлы атрибуции из исходных репозиториев/архивов.

## Ресурсы

Фактическая NVIDIA-конфигурация, число карт, стоимость, баланс и storage-тариф **не подтверждены**: Brev потребовал вход; пользователь попросил отложить этот этап. Инстансы не запускались, купон не активировался, расходы не инициировались.

[Документация Brev](https://docs.nvidia.com/brev/concepts/gpu-instances) различает stoppable и non-stoppable ресурсы: остановка не универсальна. Для поддерживающего остановку инстанса compute при stop не оплачивается, хранение может продолжать тарифицироваться. До запуска нужно проверить конкретный тип, цену диска и поведение при исчерпании кредита. Сумма $50 из задания не является проверенным балансом аккаунта.

Начать с одного GPU; 24 GB + Qwen14B NF4 — предварительный эксперимент, 40–48 GB BF16 — вариант сравнения. Обе оценки нуждаются в измерении пика памяти и времени на одной записи. GPU 80 GB не считаем пределом или обязательным минимумом; несколько карт в коде не включаются автоматически.
