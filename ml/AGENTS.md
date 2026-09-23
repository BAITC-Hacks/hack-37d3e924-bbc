# ML Ownership

Own `ml/**`, root `README.md`, ML documentation, and `JUDGE_REPORT.md`.

Read `../ARCHITECTURE.md`, `../docs/ML_CONTRACT.md`, and `../backlog/ML.md` before implementation.

## Responsibilities

- Dataset inspection, cleaning, leakage checks, preprocessing, feature engineering.
- Deterministic train/validation/test split.
- Baseline and selected explainable model.
- Honest evaluation with task-appropriate metrics.
- Serialized artifact and one stable inference function.
- Model metadata, inference tests, README ML section, final rubric audit.

## Boundaries

- Do not modify `frontend/**`, `backend/**`, DB code, API routes, or Compose.
- Do not generate random or hardcoded predictions/confidence.
- Do not leak the target, future data, IDs, or post-outcome features.
- Do not choose metrics until classification/regression and business cost are understood.

## Reproducibility

- Use deterministic seeds such as `random_state=42`.
- Training and inference must use the same saved preprocessing pipeline.
- Store production artifacts under `ml/artifacts/`.
- Save metadata with model/version/features/metrics/data split information.

## Verification

Run the project's ML tests plus:

1. train or load the final artifact;
2. load it in a fresh process;
3. predict one valid example;
4. reject one invalid example cleanly;
5. confirm output exactly matches `ML_CONTRACT.md`.

