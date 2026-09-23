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
2. `contracts/API.md`
3. `ARCHITECTURE.md`
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


## Meeting protocol project override — 2026-09-23

The team lead's current product instructions supersede the old three-role template above and legacy role guidance for this project.

- Participant 1 owns ai/ and AI-specific dependencies/instructions. The interface is ai.pipeline.run_pipeline(input_data, on_progress=None). No separate AI backend.
- Participant 2 owns backend/ AND frontend/, SQLite storage, the separate worker, review persistence and DOCX export.
- The team lead owns contracts/, shared launch configuration, README, acceptance and integration. Do not delegate both implementation lanes to the team lead.
- contracts/ is the schema source of truth; contracts/API.md and ARCHITECTURE.md describe the proposed integration. Current run and acceptance instructions are in README.md; historical backlogs were consolidated.
- Old ml/ ownership, PostgreSQL defaults and classifier/predict contracts are obsolete for this case. Legacy role skills requiring those assumptions must not be applied unchanged.
- Audio and meeting text must never go to external cloud APIs. No automatic cloud fallback. Prepare local weights/dependencies, then verify offline processing.
- Fixtures must be explicitly marked synthetic. Never report a fixture run as model quality evidence.
- Shared contract/configuration changes belong to the team lead and are communicated to both participants together; FROZEN requires actual agreement, not an assumed approval.
