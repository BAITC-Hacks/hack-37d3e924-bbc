# Architecture

Status: `DRAFT | FROZEN`

## Problem

<!-- One paragraph: what user problem are we solving? -->

## Primary user

<!-- Who uses the product? -->

## P0 vertical slice

```text
USER
  -> FRONTEND ACTION
  -> API ENDPOINT
  -> BUSINESS LOGIC
  -> DATABASE / ML
  -> API RESULT
  -> FRONTEND DISPLAY
```

## Components

| Component | Technology | Responsibility | Owner |
|---|---|---|---|
| Frontend | React + TypeScript + Vite | UI, forms, API client, result display | Frontend |
| Backend | FastAPI + Pydantic + SQLAlchemy | API, validation, business logic, persistence | Backend |
| Database | PostgreSQL | Persistent application data | Backend |
| ML | pandas + scikit-learn + joblib | Training, artifact, deterministic inference | ML |

## Decisions

| Decision | Choice | Reason |
|---|---|---|
| Deployment | Docker Compose | One-command reproducibility |
| API | REST/JSON | Fast and transparent integration |
| ML integration | In-process adapter by default | Avoid an unnecessary service boundary |

## Non-goals

- No microservices unless the case explicitly requires them.
- No Kafka, Kubernetes, Celery, or speculative infrastructure.
- No optional feature before the P0 flow works end to end.

## Environment

<!-- List required environment variables without values. -->

## Risks

| Risk | Mitigation | Owner |
|---|---|---|
| Contract drift | Freeze two contracts before coding | All |
| Model artifact mismatch | Smoke-test load + inference | ML |
| Clean-start failure | Rebuild Compose before freeze | Backend |

