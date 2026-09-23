---
name: backend-ship
description: Autonomously implement Backend and technical integration work for this three-person hackathon project. Use for FastAPI, Pydantic, PostgreSQL, migrations, business logic, ML adapter, backend tests, Dockerfiles, root Compose, environment template, and verified merges. Never use it to build UI or train the model.
---

# Backend Ship

Read `AGENTS.md`, `backend/AGENTS.md`, `ARCHITECTURE.md`, both contracts, and `backlog/BACKEND.md`.

## Loop

1. Pick the highest-priority unchecked Backend item that unblocks the P0 flow.
2. Inspect actual code before editing.
3. Implement the smallest complete change within Backend ownership.
4. Keep routers thin; put business rules in services and persistence in repositories.
5. Consume ML only through the frozen ML contract.
6. Run import, test, lint, migration, and relevant Compose checks.
7. Inspect `git diff`, `git diff --check`, secrets, validation, and ownership.
8. Commit one logical unit.
9. Check the backlog item only after verification.
10. Continue through P0, then P1.

## Merge gate

Before merging another role:

1. inspect its diff;
2. reject out-of-ownership changes;
3. verify contract compatibility;
4. run that role's relevant check;
5. merge without discarding either side blindly;
6. re-run the integrated P0 path.

## Stop conditions

Stop when requirements are genuinely ambiguous, an approved contract change is missing, credentials/external access are required, or repeated failures require a joint architecture decision.

