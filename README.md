# PROJECT NAME

<!-- ML owner maintains this file; all owners provide verified commands/details. -->

## Problem

<!-- What problem exists, for whom, and why it matters. -->

## Solution

<!-- What the product does in one short paragraph. -->

## Primary demo flow

```text
User -> Frontend -> Backend -> Database / ML -> Result
```

## Architecture

| Layer | Technology | Responsibility |
|---|---|---|
| Frontend | React, TypeScript, Vite | UI and API client |
| Backend | FastAPI, Pydantic, SQLAlchemy | API, validation, business logic |
| Database | PostgreSQL | Persistence |
| ML | pandas, scikit-learn, joblib | Training and inference |

## ML approach

<!-- Dataset, target, split, preprocessing, model, metrics, leakage controls, limitations. -->

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

Frontend: `http://localhost:<PORT>`

API docs: `http://localhost:<PORT>/docs`

Health: `http://localhost:<PORT>/health`

## Environment variables

| Variable | Required | Meaning | Example |
|---|---:|---|---|
| `DATABASE_URL` | yes | PostgreSQL connection string | `postgresql+asyncpg://...` |

Never place real secrets in this table.

## Demo

1. Open the Frontend.
2. <!-- Enter... -->
3. <!-- Submit... -->
4. <!-- Observe real result... -->

## API summary

See `docs/API_CONTRACT.md` for exact schemas.

## Tests

```bash
# Backend
cd backend && pytest -q

# Frontend
cd frontend && npm run build

# ML
# Replace with the verified command
```

## Known limitations

- <!-- honest limitation -->

