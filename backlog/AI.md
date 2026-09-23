# AI Backlog

Deadline: 23.09, 18:00 GMT+5. Current assumption: about 3h20m remain from coordination start. Owner: Participant 1. Scope: `ai/**` only.

The AI module must be locally deployable and must not send audio, transcripts, prompts, summaries, extracted tasks, or demo meeting results to external cloud APIs. OpenAI API may be used only for code and engineering help without any meeting content.

## P0 - 15:00 fixture and resource decision

- [ ] Priority P0. Result: actual GPU/balance/tariff note with recommended first configuration. DoD: list available GPU models, actual card counts and VRAM, price, remaining personal GPU budget, RAM, disk, CUDA, driver, storage/stopped-instance billing, license/gated-weight constraints, pinned model revisions/versions, expected runtime risk, and no assumption that team balances can be pooled. Dependency: GPU provider account. If access is missing, report the exact provider/login invitation or SSH access needed and continue the fixture/interface work. Owner: AI.
- [ ] Priority P0. Result: `ai/pipeline.py` exposes `run_pipeline(input_data, on_progress=None)`. DoD: importable function accepts the contract input and returns schema-compatible data for the shared synthetic fixture path. Dependency: `contracts/README.md`, `contracts/input.schema.json`, `contracts/result.schema.json`, `contracts/examples/input.json`, `contracts/examples/result.json`. Owner: AI.
- [ ] Priority P0. Result: first synthetic test JSON. DoD: passes result schema validation, preserves source language without translation, contains segments, participants, tasks, summary, warnings, and valid references. Dependency: contract fixture. Owner: AI.

## P0 - 15:45 real worker candidate

- [ ] Priority P0. Result: first local experiment on a short mixed RU/KZ recording with two speakers. DoD: transcript segments include speaker IDs and original start/end seconds; record wall time, peak VRAM/RAM, model revisions and observed transcription/diarization errors. Dependency: resource check and synthetic/anonymized audio. Owner: AI.
- [ ] Priority P0. Result: diarization experiment. DoD: at least two speaker tracks are produced; if diarization fails, the job is not accepted as meeting the mandatory demo requirement. No invented participant names. Dependency: selected local diarization model. Owner: AI.
- [ ] Priority P0. Result: local extraction and summary experiment. DoD: tasks include assignee/date only when evidence exists; relative dates are resolved from `meeting_datetime` and `timezone`; unknown due date is `null`; non-task utterances are ignored. Dependency: transcript segments. Owner: AI.
- [ ] Priority P0. Result: schema validation before returning from pipeline. DoD: invalid internal output raises an exception so backend marks the job `failed`; it must not be hidden as a successful result with `warnings`. Dependency: result schema. Owner: AI.

## P1 - 16:30 acceptance evidence

- [ ] Priority P1. Result: RU, KZ, and mixed short-recording evidence. DoD: each run has input, result JSON, timing, GPU used, model versions, and known limitations. Dependency: three demo recordings. Owner: AI.
- [ ] Priority P1. Result: chunking for long audio. DoD: a boundary test proves original timings, overlap deduplication and valid source segment IDs; an unimplemented plan is not completion. Dependency: first real run. Owner: AI.
- [ ] Priority P1. Result: offline/local operation note. DoD: documents exact model paths or download steps and confirms no external inference fallback. Dependency: selected candidates. Owner: AI.

## Guardrails

- Candidate models are starting points only: faster-whisper large-v3, pyannote Community-1, Qwen3-14B.
- Do not create a second backend or independent API server.
- Treat instructions spoken inside recordings as untrusted meeting content.
- Do not translate source speech unless a later agreed contract explicitly adds translation.
- Do not fake final demo outputs. Synthetic fixture is allowed only for integration before real evidence.

## P1 — после исправления интеграции 23.09

- [ ] Измерить семантическую сверку поручений на длинной RU/KZ/mixed записи с эталоном: одинаковые задачи разными словами, новое поручение тому же человеку, поздняя смена срока без повторения действия. Сравнить пропуски/ложные объединения; неоднозначные случаи должны оставаться на проверку. Unit tests и один synthetic real-model smoke этого не заменяют.
- [ ] Запустить согласованный CUDA-профиль с локальными весами на целевой карте и записать RAM/VRAM, время и ошибки. Mac smoke не подтверждает GPU-деплой.
