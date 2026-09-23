# API Contract — Frontend ↔ Backend

Status: `DRAFT | FROZEN`
Contract owner after freeze: Backend

## Global conventions

- Base URL: `/api/v1`
- Content type: `application/json`
- Datetime format: ISO 8601 UTC
- IDs: strings unless explicitly stated otherwise

## Error envelope

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable message",
    "details": {}
  }
}
```

## Health

### `GET /health`

Response `200`:

```json
{"status":"ok"}
```

## Primary endpoint

### `<METHOD> /api/v1/<resource>`

Purpose: <!-- what user action this supports -->

Authentication: `none | bearer token`

Request:

```json
{
  "field": "value"
}
```

Validation:

| Field | Type | Required | Constraints |
|---|---|---:|---|
| `field` | string | yes | non-empty |

Success response `200/201`:

```json
{
  "id": "...",
  "result": {}
}
```

Errors:

| Status | Code | Condition |
|---:|---|---|
| 400 | `VALIDATION_ERROR` | Invalid business input |
| 401 | `UNAUTHORIZED` | Missing/invalid auth when required |
| 404 | `NOT_FOUND` | Resource does not exist |
| 422 | `REQUEST_SCHEMA_ERROR` | Malformed request |
| 500 | `INTERNAL_ERROR` | Unexpected failure without leaked details |

## Contract test examples

Valid request:

```json
{}
```

Invalid request:

```json
{}
```

