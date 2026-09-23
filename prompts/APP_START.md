# APP Start Prompt

Ты участник 2 и владеешь `backend/**` и `frontend/**`.

Цель демо: загрузка аудио -> очередь/worker -> результат AI -> ручная проверка -> экспорт DOCX. Нельзя отправлять аудио или текст совещаний во внешние облачные API. Backend должен запускать AI через отдельный worker-процесс, который вызывает `ai.pipeline.run_pipeline(input_data, on_progress=None)`.

Сначала прочитай:

- `docs/API_CONTRACT.md`
- `contracts/README.md`
- `contracts/input.schema.json`
- `contracts/result.schema.json`
- `contracts/examples/input.json`
- `contracts/examples/result.json`
- `backlog/APP.md`

Первый отчёт в чат тимлиду:

1. что уже есть в `backend/**` и `frontend/**`;
2. какой endpoint/UI flow делаешь первым к 15:00;
3. где будет храниться original AI result и edited review result;
4. как запускается worker и как показывается real processing stage без fake percent.

P0 поведение:

- upload audio with meeting datetime, timezone, participants;
- list meetings with title/status/current stage;
- open meeting detail and render fixture result safely;
- worker status: `queued`, `processing`, `done`, `failed`;
- store current processing stage separately from final result;
- keep original result separate from edited result;
- allow reviewer edits for participants, tasks, and summary;
- show source links from tasks to transcript segments;
- retry failed jobs;
- delete meetings while respecting processing state; processing delete returns 409;
- export reviewed result to DOCX.

Правила:

- do not create a second AI backend;
- do not invent contract fields;
- no mocked final flow; fixture is only for early integration;
- render meeting text as text, not HTML;
- invalid schema/result/upload should produce clear user-visible errors.
