# Product Spitballing Sessions

Informal meetings where Claude role-plays multiple PMs to pitch feature
ideas, bugs, or changes. Andy judges which pitches become GitHub issues.
Rejected pitches stay in the file so we don't re-pitch them in three
months.

## Format

- One file per session: `YYYY-MM-DD.md`
- Many pitches per session (typically 4–8)
- See `TEMPLATE.md` for the pitch structure
- Tone is informal — PMs can disagree, push back, or build on each
  other's pitches. Capture cross-persona debate in the "Notes / side
  discussions" section; it's often more valuable than the pitches
  themselves

## Personas

Core personas (always present unless a session is narrowly scoped):

- **Commuter PM** — daily-user UX, friction, "would my mom use this"
- **Growth PM** — acquisition, ASO, conversion, virality, freemium tuning
- **Platform PM** — reliability, performance, infra, data quality, tech debt
- **OSS/Community PM** — contributor experience, docs, governance, developer inbound

**Add new personas whenever useful.** If a pitch naturally calls for a
voice the core four don't cover, introduce a new persona mid-session
and add them to the "PMs present" list at the top. Examples of personas
that might show up:

- **Data/ML PM** — for prediction-model, data quality, or ML pipeline pitches
- **Design PM** — for visual identity, branding, or UI polish pitches
- **Revenue PM** — for pricing, tier structure, or monetization deep-dives
- **Partnerships PM** — for transit agency relationships or B2B plays

Don't over-specialize. If a new persona only shows up once, fold their
pitch back under the closest core persona next session.

## Verdicts

Each pitch gets one of:

- `pending` — not yet judged
- `accepted → #NNN` — GitHub issue created
- `rejected — [reason]` — one-line reason required

Andy is the sole judge. PMs pitch; they don't vote.

## Bidirectional linking

When a pitch becomes an issue:

1. Update the session file verdict to `accepted → #NNN`
2. Add to the issue body: `Spitballed in meeting-notes/spitballing/YYYY-MM-DD.md`

Makes it easy to navigate from either direction and to audit which
ideas stuck.
