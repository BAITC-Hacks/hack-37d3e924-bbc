# Design

## Source of truth
- Status: Active. Last refreshed: 2026-09-23.
- Primary surfaces: React/FastAPI at port 8000; existing Streamlit prototype at 8501.
- Evidence: `frontend/src/main.tsx`, `frontend/src/style.css`, `prototypes/meeting-mvp/app.py`, `ARCHITECTURE.md`, `contracts/`, `docs/API_CONTRACT.md`. No separate brand assets or approved visual references are present.
- This brief follows the user's request to improve both UX and frontend while preserving existing models and working behaviour.

## Brand
- Хаттама: calm, precise, useful working software for meeting secretaries and team leads.
- Trust comes from visible sources, honest uncertainty, saved-state feedback and explicit demo labels.
- Avoid decorative dashboards, invented metrics, purple gradients, glass panels, oversized marketing blocks during review and external font/image requests.

## Product goals
- Make the next action obvious: add a recording, wait for an actual processing stage, review evidence, save, export.
- Reduce scanning effort when reviewing owners, dates and transcript evidence.
- Preserve review edits and separate original machine output; explain why an action is unavailable.
- Non-goals: new models, cloud inference, new API contracts, live meetings, authentication redesign.
- Success: full synthetic UI scenario completes, saved edits reopen, export uses saved data, keyboard and narrow-screen operation work.

## Personas and jobs
- Team lead/secretary: turns a recording into an accountable list of actions and a checked document.
- Reviewer: checks uncertain owners/dates against exact source segments.
- Hackathon demonstrator: distinguishes tested UI from real model quality and shows a reproducible flow.

## Information architecture
- Sidebar: product identity, new meeting, searchable saved meetings and local processing note.
- New meeting: heading, audio selection, factual date/time and timezone, optional participants, one primary action.
- Processing: title, explicit real stage, persistent meeting entry and useful recovery/error action. No invented percentage.
- Review: summary, participants, tasks, transcript/evidence; easy source navigation and a persistent save/export area.
- Original JSON and detailed model diagnostics remain secondary disclosures.

## Design principles
- Sources before confidence: uncertainty is explicit and never filled with invented values.
- One clear primary action per context; destructive actions are separated and confirmed.
- Progressive disclosure: advanced settings and long source lists should not obscure current work.
- Use the existing framework's controls; do not build a second app or a large design-system dependency.

## Visual language
- Canvas #f6f5f0, white surfaces, sidebar #173d35, ink #1d302a, muted text #64736c, accent #26725c, subtle borders #dce3db.
- Amber for needs-review/demo, red for errors, green for saved/done. Pair colour with words/icons.
- System font stack with Cyrillic/Kazakh coverage; headings 28–40 px desktop, 24–30 px mobile, body 14–16 px, line height 1.5–1.65.
- Spacing rhythm 4/8/12/16/24/32; sidebar about 260 px, content max-width 1200 px; review uses available width.
- Cards 12–18 px radius with light borders; quiet shadows only where hierarchy needs them.
- Small functional inline SVG icons/CSS shapes; no remote assets. Motion limited to short state feedback, respecting reduced motion.

## Components
- Reuse current forms, API client, upload endpoint, status polling, review/save/export functions and Streamlit controls.
- Improve meeting navigation, file drop zone, step navigation, status badges, source links, task cards, save bar, empty/error states.
- Frontend owns React tokens/components; prototype owns its scoped CSS. Colours and terminology should stay consistent.

## Accessibility
- Target WCAG 2.2 AA for modified controls, without claiming a certified audit.
- Real labels, semantic headings/buttons/landmarks, visible keyboard focus, labelled icon-only controls.
- Text contrast, 40–44 px hit targets, no colour-only states, status live regions with restrained announcements.
- No user/meeting text interpreted as HTML or Markdown. Respect prefers-reduced-motion.

## Responsive behavior
- Desktop >=1100 px: persistent sidebar and spacious content; useful review columns where readable.
- Tablet 760–1099 px: narrower navigation and stacked review content.
- Mobile <760 px: compact navigation, single-column forms/cards, wrapping actions, no page-wide horizontal scrolling.
- Source lists and long words wrap; sticky actions must not cover last fields or focused controls.

## Interaction states
- Loading: indicate the operation and disable duplicate submissions; retain entered data after recoverable errors.
- Empty: brief explanation plus relevant primary action, no fake meetings.
- Error: readable message and retry or correction; field-specific validation when available.
- Success: visible saved feedback and revision; export blocked while edits are unsaved/invalid.
- Disabled: nearby explanation, especially missing models and unresolved review sources.
- Backend unavailable: actionable local-server message; no silent cloud fallback.

## Content voice
- Russian interface. Use «совещание», «запись», «расшифровка», «поручения», «исходные реплики», «сохранить правки».
- Short concrete sentences. Unknown owner/date: «Требует уточнения».
- Date entry should be human friendly; preserve ISO8601/IANA semantics and never default meeting date to today silently.
- Explicit «Тестовый режим» wherever fixture output is shown; it is not evidence of model processing.

## Implementation constraints
- Existing React/TypeScript/Vite, plain CSS, Streamlit, FastAPI/SQLite. No new runtime dependencies for styling.
- Preserve contract/result fields, models, offline boundary, revision conflict handling and original/review separation.
- Prepare dependencies separately; UI and model execution must not fetch CDN resources.
- Test changed date/source/dirty-state logic, run build/typecheck, existing Python regressions and browser smoke on synthetic isolated data.
- Capture desktop/mobile screenshots using synthetic data only. Real data/ and existing meeting storage are excluded from inspection.

## Open questions
- Assumption: desktop review is primary, narrow-screen access remains supported.
- No prescribed brand assets; this palette extends the existing green prototype.
- Real model availability remains a separate acceptance gate; UI improvements do not imply completed RU/KZ/mixed model evaluation.
