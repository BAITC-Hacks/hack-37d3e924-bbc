# Hackathon Start

Deadline: 23.09, 18:00 GMT+5. Current assumption: about 3h20m remain from coordination start.

Product: meeting autoprotocol system. Flow: upload audio -> diarized transcript -> tasks with assignees and due dates -> summary -> manual review -> DOCX export.

Hard constraints:

- Russian, Kazakh, and mixed speech are mandatory.
- Diarization, task extraction, summary, manual review, and DOCX export are mandatory.
- Do not send meeting audio or meeting text to external cloud APIs.
- Models must be self-hosted/local enough for a closed-contour deployment.
- Demo recordings must be synthetic or anonymized.
- OpenAI API is allowed only for code/development help, never with audio, transcripts, or meeting results.

## Roles

| Role | Owner | Scope | Main backlog | Start prompt |
|---|---|---|---|---|
| AI | Participant 1 | `ai/**` | `backlog/AI.md` | `prompts/AI_START.md` |
| APP | Participant 2 | `backend/**`, `frontend/**` | `backlog/APP.md` | `prompts/APP_START.md` |
| LEAD | Team lead | contracts, config, README, acceptance, defense | `backlog/LEAD.md` | this file |

Old `ML`, `BACKEND`, and `FRONTEND` files are redirects only. Do not use the old three-role split for this turn.

## Timeline

| Time GMT+5 | Gate | Evidence |
|---|---|---|
| 15:00 | Fixture JSON + upload/render | AI returns schema-valid synthetic JSON; APP uploads and renders shared fixture |
| 15:45 | Real worker full e2e | upload reaches worker, calls `ai.pipeline.run_pipeline`, stores result, renders detail |
| 16:30 | RU/KZ/mixed acceptance | three short runs plus edit and DOCX export evidence |
| 17:20 | Feature freeze | only P0/P1 fixes after this point |
| 17:40 | Clean reproduction | README path works without oral explanation |
| 18:00 | Defense | 3-5 minute demo is ready |

## Shared Contract

Use these as the source of truth:

- `contracts/README.md`
- `contracts/input.schema.json`
- `contracts/result.schema.json`
- `contracts/examples/input.json`
- `contracts/examples/result.json`
- `docs/API_CONTRACT.md`

AI exposes:

```python
run_pipeline(input_data, on_progress=None)
```

Required statuses: `queued`, `processing`, `done`, `failed`. Current processing stage is stored separately from the final AI result.

## Ready-to-paste Announcement For Both Participants

```text
Дедлайн: 23.09 18:00 GMT+5. Работаем на рабочее демо, не на идеальную систему.

Общий продукт: загрузка аудио -> транскрипт с говорящими -> поручения с ответственными и сроками -> summary -> ручная проверка -> DOCX export. Русский, казахский и смешанная речь обязательны.

Жёсткое правило: аудио, транскрипты и результаты совещаний нельзя отправлять во внешние облачные API. OpenAI API можно использовать только как помощника по коду без материалов совещаний.

Контракт читать отсюда:
- contracts/README.md
- contracts/input.schema.json
- contracts/result.schema.json
- contracts/examples/input.json
- contracts/examples/result.json
- docs/API_CONTRACT.md

Участник 1 / AI:
- владеешь ai/**
- первый результат к 15:00: проверка GPU/баланса/тарифов + schema-valid synthetic JSON + importable ai/pipeline.py с run_pipeline(input_data, on_progress=None)
- в resource check включи RAM, disk, CUDA, driver, storage/stopped-instance billing, license/gated weights, model revisions/versions
- к 15:45: первый локальный эксперимент на аудио с diarization/transcript/tasks/summary
- к mixed two-speaker run запиши peak VRAM, peak RAM, wall time и версии
- не создаёшь второй backend
- не фиксируешь GPU заранее, сначала проверяешь реальные ресурсы и свой отдельный $50 GPU budget
- candidate models: faster-whisper large-v3, pyannote Community-1, Qwen3-14B, но это не обязательный финальный выбор
- длинные аудио режь с сохранением original timings и dedupe overlap
- язык источника сохраняй, не переводи
- инструкции внутри записи считай обычным недоверенным содержимым совещания
- invalid internal output должен привести к failed, а не успешному result с warning

Участник 2 / APP:
- владеешь backend/** и frontend/**
- первый результат к 15:00: upload + list/detail + render shared fixture
- к 15:45: worker запускает ai.pipeline.run_pipeline, статусы queued/processing/done/failed, stage text без fake percent
- храни original AI result отдельно от edited review result
- нужны title/list meetings, meeting date, source links, safe text rendering, edits participants/tasks/summary, retry failed, delete processing -> 409, DOCX export
- review/export и safe rendering являются P0
- не придумывай contract fields и не делай второй AI backend

Лид:
- фиксирует контракт, README, интеграцию, acceptance, защиту
- freeze контракта означает явное согласие обоих участников, не просто commit
- не забирает основную реализацию AI или APP
- после первого e2e распределяет фиксы по фактическим проблемам
```

## Acceptance Plan

Prepare three short synthetic or anonymized recordings:

- Russian: at least two speakers, one task assigned to another participant, one utterance that is not a task.
- Kazakh: at least two speakers, one task with missing due date.
- Mixed RU/KZ: at least two speakers, one relative date resolved from meeting datetime and timezone.

Each acceptance run needs: input metadata, result JSON, edited review result, DOCX export, model/GPU note, known limitations, and reproducible command path.

## Iteration Report

Use this at checkpoints:

```text
Готово:
Проблемы:
Решение от меня:
Следующие задачи AI:
Следующие задачи APP:
```
