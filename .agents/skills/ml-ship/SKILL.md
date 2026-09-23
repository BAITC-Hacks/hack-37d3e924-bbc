---
name: ml-ship
description: Autonomously implement real reproducible ML work inside ml/** and maintain the project README for this three-person hackathon. Use for dataset inspection, leakage prevention, preprocessing, training, evaluation, artifact serialization, stable inference, tests, metrics, limitations, and ML documentation. Never use it to edit Frontend, Backend, API routes, database code, or Compose.
---

# ML Ship

Read `AGENTS.md`, `ml/AGENTS.md`, `ARCHITECTURE.md`, `docs/ML_CONTRACT.md`, and `backlog/ML.md`.

## Loop

1. Pick the highest-priority unchecked ML item that unblocks inference.
2. Inspect the data and current ML code; do not assume schema or task type.
3. Check leakage and define a deterministic split.
4. Build one shared fitted pipeline for preprocessing and model inference.
5. Establish a simple baseline before tuning.
6. Evaluate with task-appropriate metrics and record limitations honestly.
7. Serialize artifact plus metadata under `ml/artifacts/`.
8. Load the artifact in a fresh process and run valid/invalid inference examples.
9. Verify output exactly matches the ML contract.
10. Inspect the diff, commit one logical unit, and update the backlog.

## README duty

Keep README concise but sufficient for judging: problem, solution, architecture, stack, real ML approach, metrics, setup, environment, Docker start, demo flow, API summary, tests, and limitations.

## Stop conditions

Stop when the target is unclear, required data is missing, leakage cannot be ruled out, the contract is incompatible, or work would require editing Frontend/Backend/Compose.

