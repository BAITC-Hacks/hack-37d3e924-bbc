# LEAD Backlog

Deadline: 23.09, 18:00 GMT+5. Owner: team lead. Scope: contracts, launch configuration, README, acceptance, integration coordination, and defense. The lead does not take over core AI or app implementation.

Current known answers: deadline is 23.09 18:00 GMT+5. Repository status from inspection: coordination/templates are present, product implementation is not proven here. Unknowns: exact skills of Participant 1 and Participant 2, exact GPU provider/card/tariff, and DOCX source contents.

## P0 - 15:00 contract and first split

- [ ] Priority P0. Result: freeze shared contract. DoD: `contracts/README.md`, `contracts/input.schema.json`, `contracts/result.schema.json`, `contracts/examples/input.json`, `contracts/examples/result.json`, and `docs/API_CONTRACT.md` are distributed and explicitly accepted by both participants. Dependency: current product requirements. Owner: Lead.
- [ ] Priority P0. Result: both participants receive the same announcement. DoD: AI and APP owners have identical contract links, timeline, and guardrails. Dependency: `START_HERE.md`. Owner: Lead.
- [ ] Priority P0. Result: integration checklist. DoD: explicit smoke path exists from upload to fixture render before real AI is ready. Dependency: APP fixture render and AI test JSON. Owner: Lead.

## P0 - 15:45 first e2e

- [ ] Priority P0. Result: early full path. DoD: one upload reaches worker, calls `ai.pipeline.run_pipeline`, stores result, and renders detail page. Dependency: AI importable pipeline and APP worker. Owner: Lead coordinates, AI/APP implement.
- [ ] Priority P0. Result: issue split after first run. DoD: every failure is assigned to AI, APP, or Lead contract/config with owner and next command/request. Dependency: first e2e evidence. Owner: Lead.

## P1 - 16:30 acceptance evidence

- [ ] Priority P1. Result: three demo recordings. DoD: Russian, Kazakh, and mixed speech; each has at least two speakers; includes one task to another participant, one missing deadline, one relative date, and one utterance that is not a task. Dependency: synthetic/anonymized recordings. Owner: Lead prepares acceptance, AI/APP run.
- [ ] Priority P1. Result: review and export proof. DoD: a reviewer edits participant/task/summary data, exports DOCX, opens it, and confirms readable content and source links. Dependency: APP review/export. Owner: Lead accepts.
- [ ] Priority P1. Result: cost log. DoD: GPU spend, card type, run time, and reason for any extra GPU are recorded; no pooled balance assumption. Dependency: AI resource check. Owner: Lead.

## P1 - 17:20 freeze to 17:40 clean repro

- [ ] Priority P1. Result: feature freeze at 17:20. DoD: no optional features start after freeze; only P0/P1 fixes. Dependency: integration state. Owner: Lead.
- [ ] Priority P1. Result: reproducibility pass by 17:40. DoD: clean setup/run instructions work, README includes closed-contour note, architecture, demo steps, limitations, and troubleshooting. Dependency: app launch and AI setup notes. Owner: Lead.
- [ ] Priority P1. Result: 3-5 minute defense. DoD: script covers problem, working scenario, architecture, checked results, limitations, and next steps. Dependency: acceptance evidence. Owner: Lead.

## Iteration Report Format

Use this format for each checkpoint:

```text
Готово:
Проблемы:
Решение от меня:
Следующие задачи AI:
Следующие задачи APP:
```

## P1 — оставшаяся приёмка после интеграции 23.09

- [ ] Повторить основной real-сценарий с запрещённым исходящим трафиком на уровне ОС/контейнера. Проверить новый запуск и отсутствие внешних зависимостей; Python offline-флаги не считаются полной сетевой изоляцией.
- [ ] С участником AI проверить реальную RU/KZ/mixed выборку по ручному эталону. JUDGE_REPORT.md разделяет smoke на синтетической озвучке и измерение качества.
