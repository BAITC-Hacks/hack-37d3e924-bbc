# Frontend Ownership

Own only `frontend/**`.

Read `../ARCHITECTURE.md`, `../docs/API_CONTRACT.md`, and `../backlog/FRONTEND.md` before implementation.

## Responsibilities

- React/TypeScript pages, components, routes, forms, and responsive UX.
- Client validation, loading, empty, success, and error states.
- Centralized API client and types that exactly match the frozen contract.
- Frontend tests, production build, frontend Dockerfile, and web-server config.

## Boundaries

- Do not modify `backend/**`, `ml/**`, database migrations, or `docker-compose.yml`.
- Do not embed business rules that belong to Backend.
- Do not leave mock data or fake API responses in the final P0 flow.
- If the API contract is insufficient, use the shared contract-change protocol; do not guess.

## Suggested structure

```text
src/
  api/
  components/
  features/
  hooks/
  pages/
  types/
```

All HTTP calls go through `src/api/`.

## Verification

Use the package manager already present. Minimum expected checks:

```bash
npm run build
npm run lint
npm test -- --run
```

If a script does not exist, do not invent success; record the missing check in the backlog.

