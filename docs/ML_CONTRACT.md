# ML Contract — Backend ↔ ML

Status: `DRAFT | FROZEN`
Contract owner after freeze: Backend, with ML approval

## Task

Problem type: `classification | regression | ranking | anomaly detection`

Target: <!-- exact target and meaning -->

Inference entry point:

```python
predict(input_data: PredictionInput) -> PredictionResult
```

## Input

```json
{
  "feature_a": 0.0,
  "feature_b": "value"
}
```

| Feature | Type | Required | Constraints | Training source |
|---|---|---:|---|---|
| `feature_a` | float | yes | finite | column name |
| `feature_b` | string | yes | allowed categories | column name |

## Output

```json
{
  "prediction": 0,
  "confidence": 0.0,
  "model_version": "1.0.0"
}
```

| Field | Type | Range/values | Meaning |
|---|---|---|---|
| `prediction` | number/string | task-specific | final model output |
| `confidence` | float/null | `0.0..1.0` or null | only if statistically meaningful |
| `model_version` | string | semantic version | artifact version |

## Invalid input behavior

- Missing feature: raise a typed validation error.
- Unknown category: define fallback or reject explicitly.
- NaN/infinite numeric value: reject or transform consistently.
- Never silently reorder unnamed feature arrays.

## Artifact

- Path: `ml/artifacts/model.joblib`
- Metadata: `ml/artifacts/metadata.json`
- Preprocessing: bundled in the same fitted pipeline whenever possible.

## Acceptance checks

- Fresh-process artifact load succeeds.
- Same input produces deterministic output.
- Training/inference feature order matches.
- Output serializes to the exact JSON shape above.

