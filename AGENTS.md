# Shared Hackathon Rules

## Mission

Ship one real, reproducible P0 vertical slice before adding secondary features.

Priority order: P0 core flow > P1 reproducibility/judging > P2 polish > P3 optional work.

## Team ownership

- Frontend owns `frontend/**` and may read shared contracts.
- Backend owns `backend/**`, `docker-compose.yml`, `.env.example`, database integration, and final merges.
- ML owns `ml/**`, `README.md`, ML metrics documentation, and the final rubric report.
- Shared architecture and contracts are agreed together before parallel work. After contract freeze, Backend applies approved contract changes.

Never edit another role's owned files unless the responsible person explicitly asks for a narrow integration fix.

## Sources of truth

Read before implementation:

1. `ARCHITECTURE.md`
2. `docs/API_CONTRACT.md`
3. `docs/ML_CONTRACT.md`
4. your role backlog

Do not invent request fields, response fields, error shapes, database assumptions, or ML interfaces.

## Work loop

1. Select the highest-priority unchecked item from your role backlog.
2. Inspect existing code before editing.
3. Implement the smallest complete change inside your ownership.
4. Run role-specific verification.
5. Inspect `git diff` and `git diff --check`.
6. Commit one logical unit.
7. Mark a backlog item done only after verification.

## Safety and quality

- Preserve uncommitted work.
- Never commit secrets or `.env`.
- No hardcoded predictions, random scores, fake API responses, or fake metrics in the final flow.
- Avoid unrelated refactoring and new major dependencies.
- Validate all external input.
- Do not expose raw internal exceptions.
- Do not claim completion without test or smoke-test evidence.

## Contract-change protocol

If a contract is insufficient:

1. Stop the affected implementation.
2. Write the exact proposed request/response change.
3. Notify the other two owners.
4. Obtain agreement.
5. Backend updates the contract and communicates the commit.
6. All branches sync before continuing dependent work.

## Integration gates

Before merge, verify ownership boundaries, contract compatibility, relevant tests, and absence of unrelated files. Never merge solely because a PR exists.

At feature freeze, do not start optional work. Run `$judge-readiness`, turn every PARTIAL/FAIL into a P0/P1 fix, and re-run the complete scenario.

