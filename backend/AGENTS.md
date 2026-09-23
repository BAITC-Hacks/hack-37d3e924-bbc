# Backend Ownership

Own `backend/**`, root `docker-compose.yml`, root `.env.example`, database migrations, approved contract updates, and final integration merges.

Read `../ARCHITECTURE.md`, both files in `../docs/`, and `../backlog/BACKEND.md` before implementation.

## Responsibilities

- FastAPI routes and Pydantic v2 schemas.
- Service-layer business logic and repository-layer persistence.
- PostgreSQL, SQLAlchemy 2, asyncpg, Alembic.
- Authentication/authorization when required by the case.
- Error handling, tests, health endpoint, backend Dockerfile.
- ML adapter that consumes the exact ML contract.
- Clean Docker Compose startup and final merge verification.

## Request flow

```text
router -> service -> repository -> database
router -> service -> ML adapter -> ML interface/artifact
```

Keep routers thin. Never train a model inside Backend.

## Required health endpoint

```http
GET /health
```

```json
{"status":"ok"}
```

## Security

- Validate external inputs.
- Hash passwords; never store plaintext credentials.
- Never expose raw tracebacks.
- Never hardcode secrets, financial outputs, or ML results.
- Return consistent errors from the API contract.

## Verification

Adapt paths to the actual project, but preserve these checks:

```bash
python -c "import app.main"
pytest -q
ruff check .
alembic upgrade head
docker compose config
```

After integration, test `/health` and the complete P0 scenario.

