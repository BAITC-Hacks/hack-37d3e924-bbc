---
name: hackathon-intake
description: Turn a newly received hackathon case, rubric, dataset, or starter repository into one agreed P0 vertical slice, frozen Frontend-Backend and Backend-ML contracts, and three non-overlapping role backlogs. Use only at kickoff or when the official requirements materially change; do not implement features during intake.
---

# Hackathon Intake

Read the complete case, rubric, repository, dataset notes, and existing code before planning.

## Produce

Update:

- `ARCHITECTURE.md`
- `docs/API_CONTRACT.md`
- `docs/ML_CONTRACT.md`
- `backlog/FRONTEND.md`
- `backlog/BACKEND.md`
- `backlog/ML.md`

## Workflow

1. Extract explicit functional, technical, documentation, reproducibility, and reliability requirements.
2. Identify the shortest complete demonstrable user flow.
3. Write it as `user -> UI -> API -> business logic -> DB/ML -> result -> UI`.
4. Classify every requirement as P0, P1, P2, or P3.
5. Define exact JSON request/response/error shapes in the API contract.
6. Define exact typed inference input/output and artifact location in the ML contract.
7. Assign each task to exactly one owner: Frontend, Backend, or ML.
8. Record dependencies and the first integration checkpoint.
9. Check that no task appears in more than one role backlog.
10. Mark contracts `FROZEN` only after all three humans approve them.

## Rules

- Do not write application code during intake.
- Do not design optional features before the P0 slice is defined.
- Prefer the smallest architecture that satisfies the rubric.
- Flag genuine product ambiguity instead of inventing an answer.

## Exit criteria

Finish only when each role can work independently without guessing field names, output shapes, ownership, or priority.

