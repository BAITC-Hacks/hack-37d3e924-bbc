---
name: judge-readiness
description: Perform the final evidence-based hackathon jury audit after feature freeze. Use in the last 30–40 minutes to test functional completeness, real technical implementation and ML, README quality, clean reproducibility, invalid inputs, reliability, and basic security. Create JUDGE_REPORT.md and P0/P1 fixes; do not add optional features or estimate a score.
---

# Judge Readiness

Do not start optional features. Audit the repository and running application as a skeptical evaluator.

## 1. Functional completeness

Execute the primary scenario from user input to final UI result. Fail hardcoded, mocked, random, or unfinished core behavior.

## 2. Technical implementation

Inspect source code and prove Frontend, Backend, DB, and ML are genuinely connected. Confirm business logic and real model inference exist.

## 3. README and documentation

Verify README explains problem, solution, architecture, stack, ML approach and metrics, setup, environment variables, Docker startup, demo flow, API summary, tests, and limitations.

## 4. Reproducibility

Follow only repository instructions. Target a clean:

```bash
cp .env.example .env
docker compose up --build
```

Verify dependencies, configuration, DB, migrations, Backend, Frontend, and ML artifact.

## 5. Reliability and security

Test valid inputs, then empty values, invalid types, prohibited negatives, malformed IDs, missing resources, unauthenticated access when required, missing configuration, and one service failure if practical. Confirm the P0 scenario does not crash or leak internal exceptions.

## Required output

Create `JUDGE_REPORT.md`. For every rubric criterion write exactly one status: `PASS`, `PARTIAL`, or `FAIL`, followed by concrete commands, requests, files, or observed behavior as evidence.

For every PARTIAL/FAIL, add a P0/P1 repair item to the correct role backlog. Do not award points or estimate a final score.

After repairs, re-run only the affected checks plus the full P0 scenario and update the report.

