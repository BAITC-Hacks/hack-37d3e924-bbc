# ML Backlog

## P0 — Real model and inference

- [ ] Identify target, task type, business meaning, and leakage risks.
- [ ] Inspect dataset shape, dtypes, missing values, class/target distribution.
- [ ] Create deterministic train/validation/test split.
- [ ] Build preprocessing pipeline used by both training and inference.
- [ ] Train a simple baseline.
- [ ] Train/select the final model using appropriate metrics.
- [ ] Save loadable artifact and metadata.
- [ ] Implement stable `predict()` interface from `ML_CONTRACT.md`.
- [ ] Run fresh-process inference smoke test.

## P1 — Evidence and documentation

- [ ] Document dataset and feature definitions.
- [ ] Document honest metrics and limitations.
- [ ] Add inference and invalid-input tests.
- [ ] Write README sections: problem, solution, architecture, ML, setup, demo, limitations.
- [ ] Run `$judge-readiness` at feature freeze and create `JUDGE_REPORT.md`.

## P2 — Improvements

- [ ] Tune model only if baseline, artifact, contract, and P0 integration already work.
- [ ] Add explainability only if it is reliable and useful for the demo.

## Data / contract blockers

<!-- Record exact missing field, data issue, or metric risk. -->

