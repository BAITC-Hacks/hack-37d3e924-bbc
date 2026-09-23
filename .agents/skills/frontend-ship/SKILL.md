---
name: frontend-ship
description: Autonomously implement the highest-priority Frontend backlog items inside frontend/** for this three-person hackathon project. Use for React/TypeScript UI, forms, API client, states, responsiveness, frontend tests, build, and frontend container work. Never use it to edit Backend, ML, shared contracts, or root Compose.
---

# Frontend Ship

Read `AGENTS.md`, `frontend/AGENTS.md`, `ARCHITECTURE.md`, `docs/API_CONTRACT.md`, and `backlog/FRONTEND.md`.

## Loop

1. Pick the highest-priority unchecked Frontend item that unblocks the P0 flow.
2. Inspect the existing frontend architecture and package scripts.
3. Implement the smallest complete change inside `frontend/**`.
4. Route all HTTP calls through the centralized API client.
5. Match contract types exactly; never guess a field.
6. Run available build, lint, and relevant tests.
7. Inspect `git diff`, `git diff --check`, and changed-file ownership.
8. Commit one logical unit.
9. Check the backlog item only after verification.
10. Continue through P0, then P1; stop before P2 if integration is unstable.

## Integration check

For changes consuming the primary endpoint, test against the real Backend when available. A component test with mocked data does not prove the P0 flow.

## Stop conditions

Stop and report the exact blocker when the contract is ambiguous, credentials are required, the Backend response is incompatible, or work would require editing outside `frontend/**`.

