# PM.md — TrackRat Execution Tracker

> Last updated: 2026-02-08

## Role

The PM (Claude) translates the CEO's strategic plan into daily executable work. This document tracks sprint-level execution against the phases approved by the board on 2026-02-06. See `CEO.md` for strategic context and `board-meetings/` for governance decisions.

Daily standup notes are recorded in `standup-notes/`.

---

## Current Phase: Phase 1 — Fix the Funnel, Open-Source Prep & Launch

**Board target:** Week of Feb 9, 2026
**Status:** In progress — backend stabilization complete, prep work remains

### Phase 1 Execution Checklist

#### 1.1 Landing Page Overhaul (#408)

| Task | Owner | Status |
|------|-------|--------|
| Take 6-8 iPhone screenshots | Andy | Not started |
| Record 30-second screen recording | Andy | Not started |
| Gather 2-3 user testimonials | Andy | Not started |
| Redesign trackrat.net (hero, App Store badge, GitHub link, FAQ, SEO) | Claude | Not started |
| Add structured data (JSON-LD) | Claude | Not started |
| Add App Store smart banner meta tag | Claude | Not started |

#### 1.2 App Store Optimization (#409)

| Task | Owner | Status |
|------|-------|--------|
| Update keywords | Andy | Not started |
| Update subtitle | Andy | Not started |
| Upload screenshots with text overlays | Andy | Not started |
| Write keyword-rich description | Andy | Not started |
| Add 30-second App Preview video | Andy | Not started |

#### 1.3 Open-Source Prep (#339)

| Task | Owner | Status |
|------|-------|--------|
| Merge PR #368 (LIRR + Metro-North) | Claude | Done |
| Stabilize LIRR/MNR collectors (bug fixes) | Claude | Done |
| Move Android to separate private repo (#410) | Andy/Claude | Not started |
| Complete #339 (secrets audit, CORS, env docs) | Claude | Not started |
| License: Apache 2.0 | Joint | Done (resolved 2026-02-06) |
| Write README.md | Claude | Not started |
| Write CONTRIBUTING.md | Claude | Not started |
| Clean up repo (dead code, TODOs) | Claude | Not started |
| Build sharing deep links (#411) | Claude | Not started |
| Resolve Dependabot alerts (3 alerts) | Claude | Not started |

#### 1.4 Open-Source Launch & Growth (#412)

| Task | Owner | Status |
|------|-------|--------|
| Landing page live with open-source framing | Claude | Blocked (1.1) |
| Sharing deep links functional | Claude | Blocked (1.3) |
| Web app footer link to GitHub | Claude | Not started |
| Make repo public | Andy | Blocked (1.3) |
| Reddit posts (r/NJTransit, r/nycrail, etc.) | Andy | Blocked (launch) |
| Show HN post | Andy | Blocked (launch) |
| Press outreach | Andy | Blocked (launch) |

---

## What's Been Done

Recent work (last 7 days) has focused on backend stability for LIRR/Metro-North:

- Merged PR #368 (LIRR + Metro-North support)
- Fixed MNR direction inference for inbound trains stuck as SCHEDULED
- Fixed unique_journey_stop constraint violations in MNR/LIRR collectors
- Fixed MNR train ID prefix mismatch
- Fixed LIRR route topology errors on 4 branches
- Fixed GTFS backfill edge cases (all-unmapped stops, missing origin stop)
- Fixed MNR/LIRR collector MissingGreenlet crash and congestion data gaps
- Fixed NULL station_code crash and session poisoning
- Added GCP log query helper script

---

## Blockers

1. **Andy's content tasks** — Screenshots, videos, testimonials needed before landing page can ship. These are blocking 1.1 and by extension 1.4.
2. **Android repo move** — Needs to happen before repo goes public. Requires Andy's GitHub access or joint coordination.
3. **Secrets audit (#339)** — Must verify no API keys, credentials, or sensitive config leak when repo goes public.

---

## Standup Format

Daily standups are recorded in `standup-notes/YYYY-MM-DD.md`. Format:

```
# Standup — YYYY-MM-DD

## Yesterday
- What got done

## Today
- What we'll work on

## Blockers
- What's in the way

## Decisions Needed
- Questions for Andy
```

---

*This is a living document maintained by the PM (Claude). Updated at each standup.*
