# CEO.md — TrackRat Strategic Analysis

> Last updated: 2026-02-06

## Mission & Vision

TrackRat is an **open-source, general-purpose transit tracking framework** built primarily through AI-assisted "vibe coding." The mission is to grow the project, the community, and the broader transit data ecosystem. We encourage other apps and developers to take whatever they'd like from our codebase or feature set.

**This is not a competitive product.** We do not frame against Clever Commute or other transit apps. We lift the entire sector through open-source tooling and shared infrastructure.

**Governance is transparent.** Board proceedings, strategic decisions, and internal governance processes are public. See `board-meetings/` for meeting minutes.

---

## Current State Assessment

### What We Have

**Product**: A multi-platform real-time transit tracking app covering NJ Transit, Amtrak, PATH, PATCO, LIRR, and Metro-North (LIRR/Metro-North via PR #368, to be merged before open-source launch) with ML-powered track predictions, Live Activities, delay forecasting, and congestion maps.

**Platforms**:
- **iOS** (production, App Store): Full-featured — Live Activities, track predictions, congestion maps, trip history, RatSense AI, Penn Station guide, Pro subscription via StoreKit 2. Version 2.4.
- **Web** (production, GitHub Pages): Minimal MVP — station selection, departure lists, train details. Needs PWA upgrade.
- **Android** (experimental, private repo): Core features present but broken critical buttons, duplicate models, no local caching. Excluded from open-source launch. Moved to separate private repo.
- **Backend** (production, GCP Cloud Run): FastAPI + PostgreSQL, horizontal scaling, APScheduler for data collection, ML prediction pipeline. Solid.
- **Infrastructure** (production, GCP): Terraform-managed, staging + production environments, Cloud Run, Cloud SQL, monitoring dashboards.

**Metrics** (as of 2026-02-06):
- App Store: 5.0 stars, 7 ratings
- Price: Free with TrackRat Pro at $2.99/month
- 250+ stations covered
- Developer: Andrew Martin (solo)
- Launched: ~August 2025 (about 6 months live)
- Development velocity: ~215 commits in January 2026

**Online Presence**:
- Website: trackrat.net (landing page — needs redesign)
- YouTube: @TrackRat-App (shorts)
- Instagram: @trackratapp
- Feedback: trackrat.nolt.io
- No Reddit presence (yet — launch post planned)
- No press coverage (yet — outreach planned)

### Core Diagnosis

**We have a distribution crisis, not a product crisis.** The product is technically superior but nobody knows it exists. 7 ratings in 6 months indicates near-zero organic discovery. Every hour spent adding features for zero users is an hour not spent getting the product into commuters' hands.

---

## Approved Strategic Plan

*Approved by board vote on 2026-02-06. See `board-meetings/2026-02-06-board-meeting.txt` for full discussion.*

### Phase 1: Fix the Funnel & Open-Source Prep (Week 1)

#### 1.1 Landing Page Overhaul (trackrat.net)
Lead with the open-source mission: "Real-time transit predictions. Free, open source, built for the community."

**Andy's tasks:**
- [ ] Take 6-8 high-quality iPhone screenshots (departure list, track prediction, Live Activity on lock screen, congestion map, train details, trip history)
- [ ] Record 30-second screen recording of core flow
- [ ] Gather 2-3 user testimonials

**Code tasks:**
- [ ] Redesign trackrat.net with: hero video/GIF, App Store badge, "Built in the Open" section, GitHub repo link, FAQ, SEO
- [ ] Add structured data (JSON-LD) for Google indexing
- [ ] Add App Store smart banner meta tag for iOS Safari visitors

#### 1.2 App Store Optimization
**Andy's tasks:**
- [ ] Update keywords: "transit", "track prediction", "Penn Station", "train tracker", "Amtrak", "PATH train", "commute", "live activity", "open source transit"
- [ ] Update subtitle (e.g., "Open Source Transit Track Predictions")
- [ ] Upload screenshots with text overlays
- [ ] Write longer, keyword-rich description
- [ ] Add 30-second App Preview video

#### 1.3 Open-Source Prep
**Reference:** GitHub issue #339 has the pre-flight checklist.

**Code tasks:**
- [ ] Merge PR #368 (LIRR + Metro-North)
- [ ] Move Android to separate private repo
- [ ] Complete issue #339 (secrets audit, CORS config, env setup docs)
- [ ] Resolve license: currently GPL v3, board approved Apache 2.0 in principle (see Open Questions below)
- [ ] Write README.md for open-source audience
- [ ] Write CONTRIBUTING.md
- [ ] Clean up repo (dead code, TODOs, anything embarrassing)
- [ ] Build sharing deep links

### Phase 2: Open-Source Launch & Growth (Week 2)

Everything fires together as a coordinated launch:

**Andy's tasks:**
- [ ] Make repo public
- [ ] Post on r/NJTransit: honest developer post asking for feedback, mentioning open source
- [ ] Cross-post to r/nycrail, r/newjersey, r/opensource
- [ ] Respond to every comment
- [ ] Submit Show HN: "Show HN: TrackRat — Open-source ML-powered transit predictions, built by vibe coding"
- [ ] Begin content marketing: weekly transit data posts, short-form video
- [ ] Press outreach: "Developer open-sources AI-powered transit prediction framework, built almost entirely through vibe coding"
- [ ] Contact transit advocacy groups (offering free tools, not selling)
- [ ] Engage developer community (write-ups on backend architecture, ML pipeline)

**Code tasks:**
- [ ] Ensure landing page is live with open-source framing
- [ ] Sharing deep links functional
- [ ] Web app has footer link to GitHub repo

### Phase 3: Product Improvements (Weeks 2-6)

**Code tasks:**
- [ ] PWA manifest + service worker for "Add to Home Screen"
- [ ] Web Push API notification support
- [ ] Web UI improvements (closer to iOS experience)
- [ ] "Get the native app for Live Activities" banner on web
- [ ] Usage analytics integration (TelemetryDeck or similar — privacy-respecting, no personal data)
- [ ] Track: app opens, route selections, train detail views, feature usage, subscription conversion events

### Phase 4: Monetization Optimization (Weeks 8-12)

**Pricing model:** $2.99/month Pro. No changes until we have analytics data.

**Business model framing:** Code is free and open source. The hosted service (backend, ML models, 24/7 data collection) costs money to run. Users pay for the managed service, not the software. This is the standard open-source model (Red Hat, GitLab, Elastic).

**Future consideration (needs data):**
- Evaluate $1.99/month or $9.99/year recurring
- Commute Score (weekly commute stats)
- Widget support (iOS) as Pro feature
- Route alerts ("Your usual 5:15 is cancelled")
- API access tiers for developer community

### Phase 5: Platform & Framework Expansion (Weeks 10+)

- "Add a Transit System" contributor guide
- Template collector with documentation
- CI/CD for contributor PRs
- Community-driven transit system additions (SEPTA Regional Rail, MTA Subway, etc.)
- Framework vs. app branding may need to split eventually

### Phase 6: Sustainability (Ongoing)

**Technical debt:**
- Backend test coverage (limited for schedule generation)
- iOS test coverage (<10%, disabled test files exist)
- SwiftLint or equivalent
- Smarter cache invalidation (beyond time-based)
- Web app needs tests
- Resolve 3 Dependabot alerts (2 high, 1 moderate) before going public

**Governance:**
- Publish board meeting notes to repo
- Public roadmap (GitHub Projects)
- Decision log for contributors
- Contributor governance model (if community grows)

---

## What NOT to Do Right Now

1. **Don't add SEPTA/MTA yet** — Depth over breadth. Dominate the current corridor first, then let contributors expand.
2. **Don't build an Apple Watch app** — Cool but won't move growth metrics.
3. **Don't add GraphQL** — REST API is fine.
4. **Don't add WebSocket** — 30-second polling is adequate.
5. **Don't add multi-language support** — English covers the target market.
6. **Don't frame against competitors** — We lift the whole sector.

---

## Board Decisions on Record

| Decision | Resolution | Date |
|----------|-----------|------|
| Vision | Open-source general-purpose transit framework | 2026-02-06 |
| Competitor framing | None — encourage the sector | 2026-02-06 |
| Pricing | $2.99/month Pro, no changes | 2026-02-06 |
| License | Apache 2.0 (pending — currently GPL v3, needs resolution) | 2026-02-06 |
| Android | Excluded from public repo, moved to private | 2026-02-06 |
| LIRR/Metro-North | Merge PR #368 before open-source launch | 2026-02-06 |
| Infrastructure costs | Not a concern at this stage | 2026-02-06 |
| Open-source timeline | Target week of Feb 9, 2026 | 2026-02-06 |
| Governance | Public board proceedings and decision logs | 2026-02-06 |

---

## Open Questions

1. **License resolution:** Board approved Apache 2.0 in principle, but repo currently has GPL v3. GPL v3 copyleft requires derivative works to also be GPL v3 — this conflicts with the vision of letting proprietary apps freely use our code. Apache 2.0 is permissive, includes patent protection, and aligns with the stated mission. Decision needed before going public.

2. **App Store Connect analytics:** Do we have data on downloads, impressions, conversion rate? This would help baseline Phase 4 decisions.

3. **Active user estimate:** Can we estimate from API request logs before analytics is integrated?

4. **NJ Transit relationship risk:** Success could attract the same adversarial attention Clever Commute received. No action needed now, but worth monitoring.

---

## Success Metrics (30-day targets from launch)

- App Store ratings: 7 → 25+
- GitHub stars: 0 → establish baseline
- Reddit post engagement: 50+ upvotes on r/NJTransit
- Hacker News: front page
- Weekly active users: establish baseline (need analytics)
- Web app daily visitors: establish baseline
- Pro conversion rate: establish baseline
- Contributors: first external PR

---

## Appendix A: Key Codebase Reference

### Repository Structure
```
TrackRat/
├── backend_v2/          # Python FastAPI backend
│   ├── src/trackrat/    # Main source
│   │   ├── api/         # API endpoints (FastAPI routers)
│   │   ├── models/      # SQLAlchemy + Pydantic models
│   │   ├── services/    # Business logic (collectors, predictions, etc.)
│   │   └── main.py      # App entrypoint
│   ├── tests/           # pytest tests
│   └── pyproject.toml   # Poetry deps
├── ios/                 # Swift/SwiftUI iOS app
│   ├── TrackRat/
│   │   ├── Views/       # Screens/ and Components/
│   │   ├── Services/    # APIService, SubscriptionService, etc.
│   │   ├── Models/      # Data models
│   │   └── Configuration.storekit  # StoreKit config
│   └── TrackRat.xcodeproj
├── webpage_v2/          # React + TypeScript + Vite + Tailwind
│   ├── src/
│   │   ├── pages/       # TripSelectionPage, TrainListPage, TrainDetailsPage, FavoritesPage
│   │   ├── components/  # TrainCard, StationPicker, etc.
│   │   ├── services/    # api.ts, storage.ts
│   │   └── store/       # appStore.ts (Zustand)
│   └── vite.config.ts
├── trackrat.net/        # Landing page (static HTML)
├── infra_v2/            # Terraform GCP infrastructure
│   └── terraform/       # Cloud Run, Cloud SQL, etc.
├── board-meetings/      # Public board meeting minutes
├── .github/workflows/   # CI/CD (deploy-webpage.yml, etc.)
├── .claude/             # PM tooling, rules, agents
├── CEO.md               # This file (strategic direction)
└── CLAUDE.md            # Project-wide development rules
```

Note: Android has been moved to a separate private repository.

### Backend Data Collection Architecture
- **NJT/Amtrak**: Multi-phase — Schedule Generation (daily) → Discovery (30min) → Collection (15min) → JIT Updates (on-demand) → Validation (hourly)
- **PATH**: Single collector every 4 minutes using native RidePATH API, discovers at all 13 stations
- **PATCO**: GTFS static schedules from SEPTA feed, no real-time API
- **LIRR/Metro-North**: PR #368 (to be merged)

### iOS Pro Features (gated by SubscriptionService)
1. Live Activities (lock screen + Dynamic Island)
2. Track Predictions (ML platform assignments)
3. Delay Forecasts (ML delay/cancellation probability)
4. Live Congestion Map
5. Historical Analytics
6. Trip History/Statistics (beta)
7. RatSense AI (journey suggestions)
8. Penn Station Boarding Guide

### API Environments
- Production: `https://apiv2.trackrat.net/api/v2`
- Staging: `https://staging.apiv2.trackrat.net/api/v2`
- Web app: `https://bokonon1.github.io/TrackRat/`
- Landing page: `https://trackrat.net/`

### App Store Details
- App Store URL: `https://apps.apple.com/us/app/trackrat/id6746423610`
- App ID: `6746423610`
- Requires iOS 17.0+
- Developer privacy stance: "does not collect any data"

### Known Issues
- 3 Dependabot alerts (2 high, 1 moderate) — must resolve before going public
- GitHub issue #339: open-source prep checklist
- PR #368: LIRR + Metro-North support (ready to merge)

---

## Appendix B: Competitive Intelligence

*Note: We do not compete with these apps. This intelligence is for market awareness only.*

### Clever Commute
- Developer: Joshua Crandall, Montclair NJ
- Founded: 2015
- Pricing: $50/year premium
- Coverage: NJ Transit, LIRR, Metro-North
- Tech: Historical track frequency (2-month lookback)
- Press: NY Post article (Oct 2024), viral TikTok
- NJT relationship: adversarial (NJT changed API to block features)

### NJ Tracks (njtracks.app)
- Track predictions + real-time departures for NJT
- Limited public information on approach/traction

### TrackRat's Unique Attributes
1. ML predictions (not historical frequency)
2. Multi-system unified view (6 systems)
3. Open source
4. Live Activities (no other transit app has this)
5. Privacy-first (no data collection, verifiable via source code)
6. Built through vibe coding (unique development story)

---

## Appendix C: Social Channels

- YouTube: `https://www.youtube.com/@TrackRat-App/shorts`
- Instagram: `https://www.instagram.com/trackratapp/`
- Feedback portal: `https://trackrat.nolt.io/`
- Support email: `trackrat@andymartin.cc`
- GitHub: `https://github.com/bokonon1/TrackRat` (currently private, going public week of Feb 9)

---

*This is a living document maintained by the CEO (Claude) and approved by the Board (Andy). Updated after each board meeting.*
