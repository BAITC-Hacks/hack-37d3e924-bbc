# APP Backlog

Deadline: 23.09, 18:00 GMT+5. Current assumption: about 3h20m remain from coordination start. Owner: Participant 2. Scope: `backend/**` and `frontend/**`.

The app owns upload, storage, job state, worker launch, manual review, and DOCX export. It must call `ai.pipeline.run_pipeline(input_data, on_progress=None)` from a separate worker process in the baseline deployment. It must not send meeting audio or text to external APIs.

## P0 - 15:00 upload and render fixture

- [ ] Priority P0. Result: upload creates a meeting and queued job. DoD: UI can upload an audio file with meeting datetime, timezone, and participants; backend stores original file path accessible to worker. Dependency: API contract in `docs/API_CONTRACT.md`. Owner: APP.
- [ ] Priority P0. Result: meeting list and detail view. DoD: UI shows title, status, meeting date, current processing stage, and opens a meeting detail page. Dependency: stored meeting records. Owner: APP.
- [ ] Priority P0. Result: render shared synthetic result. DoD: detail page safely displays transcript segments, tasks, summary, warnings, speaker/source links, and review state from `contracts/examples/result.json`. Dependency: contract fixture. Owner: APP.

## P0 - 15:45 worker e2e

- [ ] Priority P0. Result: worker process runs AI pipeline. DoD: status moves `queued -> processing -> done` or `failed`; progress stage text is stored separately from result; no fake percentage is shown. Dependency: `ai/pipeline.py`. Owner: APP.
- [ ] Priority P0. Result: original AI result and edited review result are stored separately. DoD: reviewer edits do not overwrite raw pipeline output; reset or comparison remains possible. Dependency: database/storage model. Owner: APP.
- [ ] Priority P0. Result: retry failed job. DoD: failed meeting can be requeued without duplicating the meeting or losing original upload. Dependency: job status model. Owner: APP.
- [ ] Priority P0. Result: delete respects processing state. DoD: done/failed/queued meetings can be deleted safely; processing jobs return HTTP 409 with a clear UI message. Dependency: worker state handling. Owner: APP.

## P0 - 16:30 review and export

- [ ] Priority P0. Result: manual review edits participants, tasks, and summary. DoD: assignee IDs remain valid, source links remain visible, and invalid due dates are rejected. Dependency: result schema. Owner: APP.
- [ ] Priority P0. Result: DOCX export. DoD: exported file contains meeting metadata, participant list, transcript with speaker/time, tasks with assignee/due date/source, summary, and warnings. Dependency: reviewed result. Owner: APP.
- [ ] Priority P0. Result: safe text rendering. DoD: transcript/task/summary text is rendered as text, not HTML; long text and mixed Cyrillic/Kazakh characters remain readable. Dependency: frontend display. Owner: APP.

## P1 - 17:20 freeze and reproducibility

- [ ] Priority P1. Result: verified startup instructions delivered to the lead. DoD: exact commands start backend, frontend, worker and storage, with dependency versions and evidence of a fixture run and a real run. Dependency: working application; lead incorporates these commands into README. Owner: APP.
- [ ] Priority P1. Result: failure handling. DoD: invalid uploads, missing audio files, AI failure, and invalid result schema produce understandable UI/backend errors. Dependency: integration tests or smoke script. Owner: APP.

## Guardrails

- Do not implement a second AI backend.
- Do not invent contract fields; request contract changes from Lead.
- Do not treat fixture rendering as final demo success.
- Keep UI operational and dense enough for repeated review, not a marketing page.
