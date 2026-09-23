# Backend Backlog

## P0 — Primary demo

- [ ] Scaffold or inspect FastAPI application.
- [ ] Implement `GET /health`.
- [ ] Implement primary endpoint exactly from `API_CONTRACT.md`.
- [ ] Add Pydantic validation and consistent errors.
- [ ] Add service/repository separation where persistence is required.
- [ ] Add PostgreSQL model and migration where required.
- [ ] Implement ML adapter exactly from `ML_CONTRACT.md`.
- [ ] Prove API -> DB/ML -> response with a test or smoke script.

## P1 — Reproducibility and reliability

- [ ] Backend tests pass.
- [ ] Ruff passes.
- [ ] Migration applies on a clean database.
- [ ] Backend Dockerfile works.
- [ ] Root `docker-compose.yml` starts DB, backend, frontend, and required dependencies.
- [ ] `.env.example` lists every variable without secrets.
- [ ] Authentication/authorization is implemented if required.
- [ ] Invalid input and missing resource cases do not crash.
- [ ] Review and merge verified role branches.

## P2 — Enhancements

- [ ] Add secondary endpoints only after the P0 flow is stable.
- [ ] Add observability only if it helps the demo or debugging.

## Integration blockers

<!-- Record exact failing command/request and owner. -->

