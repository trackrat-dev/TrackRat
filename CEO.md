# CEO.md — TrackRat Strategic Analysis

> Last updated: 2026-03-19

## Mission & Vision

TrackRat is an **open-source, general-purpose transit tracking framework** built primarily through AI-assisted "vibe coding." The mission is to grow the project, the community, and the broader transit data ecosystem. We encourage other apps and developers to take whatever they'd like from our codebase or feature set.

**This is not a competitive product.** We do not frame against Clever Commute or other transit apps. We lift the entire sector through open-source tooling and shared infrastructure.

**Governance is transparent.** Board proceedings, strategic decisions, and internal governance processes are public. See `board-meetings/` for meeting minutes.

---

## Current State Assessment

### What We Have

**Product**: A multi-platform real-time transit tracking app covering **8 transit systems** — NJ Transit, Amtrak, PATH, PATCO, LIRR, Metro-North, NYC Subway, and NJ Transit service alerts — with track predictions, Live Activities, stop-level delay forecasting, route alerts, congestion maps, and morning digest notifications.

**Platforms**:
- **iOS** (production, App Store): Full-featured — Live Activities, track predictions, interactive congestion maps, route alerts with planned work notifications, morning digests, onboarding flow, Pro subscription via StoreKit 2.
- **Web** (production, trackrat.net): Landing page with open-source framing, video, FAQ. Web app with station selection, departure lists, train details, track predictions. Needs PWA upgrade.
- **Android** (experimental): Excluded from open-source launch. Still in main repo (private repo move deferred).
- **Backend** (production, GCP GCE): FastAPI + PostgreSQL, horizontal scaling via Managed Instance Groups, APScheduler for data collection, prediction pipeline.
- **Infrastructure** (production, GCP): Terraform-managed, staging + production environments, GCE Managed Instance Groups, Cloud SQL, monitoring dashboards.

**Metrics** (as of 2026-03-19):
- App Store: ~20 downloads/week (organic, zero marketing)
- 1 paying subscriber
- Price: Free with TrackRat Pro at $4.99/month (increased from $2.99 on ~2026-02)
- Freemium model: 1 free train system, 1 free route alert
- 8 transit systems, 500+ stations covered
- Developer: Andrew Martin (solo)
- Launched: ~August 2025 (about 8 months live)
- Development velocity: 931 commits between 2026-02-06 and 2026-03-19

**Online Presence**:
- Website: trackrat.net (landing page with open-source framing)
- YouTube: @TrackRat-App (shorts)
- Instagram: @trackratapp
- Feedback: trackrat.nolt.io
- No Reddit presence (yet — launch posts planned)
- No press coverage (yet — outreach planned)

### Core Diagnosis

**We have a distribution crisis, not a product crisis.** The product is comprehensive and technically strong — 8 transit systems, predictions, alerts, Live Activities — but has near-zero awareness. ~20 organic downloads/week with zero marketing effort suggests the App Store listing alone generates some interest, but no growth engine exists yet.

The board deprioritized marketing from Feb-March 2026 to ship subway support and route alerts. That work is now complete and the product is ready for public launch.

---

## Approved Strategic Plan

*Original plan approved 2026-02-06. Updated 2026-03-19 to reflect current state and revised launch sequence.*

### Phase 1: Launch (Active — Target: This Week)

The board approved a specific launch sequence on 2026-03-19:

**Pre-step: Demo Videos (Andy)**
Record 3 videos:
1. Route Alerts — subscribe, morning digest, real-time notification
2. Multimodal Trip — subway to NJ Transit, showcasing all 8 systems
3. Onboarding-to-Features — app open through first departure, incorporating Live Activities, track predictions, and congestion map

**Days 1-2: App Store Optimization (Andy)**
- Update screenshots reflecting 8 systems, route alerts, subway
- Update keywords, subtitle, description
- Upload App Store Preview video

**Day 3: Make Repo Public (Andy)**

**Days 4-5: Reddit Launch (Andy)**
- r/NJTransit, r/nycrail, r/newjersey, r/opensource
- Respond to every comment

**Days 6-7: Show HN (Andy)**
- "Show HN: TrackRat — Open-source transit predictions for 8 systems, built by vibe coding"

### Phase 2: Product Improvements (Post-Launch)

Deferred until after launch reception is assessed:
- [ ] PWA manifest + service worker
- [ ] Web Push notifications
- [ ] Usage analytics (TelemetryDeck or similar, privacy-respecting)
- [ ] Sharing deep links
- [ ] JSON-LD structured data for SEO

### Phase 3: Monetization Optimization (Post-Analytics)

**Current pricing:** $4.99/month Pro with freemium tier (1 system, 1 alert free).

**Business model framing:** Code is free and open source. The hosted service (backend, predictions, 24/7 data collection) costs money to run. Users pay for the managed service, not the software. Standard open-source model (Red Hat, GitLab, Elastic).

**Future consideration (needs usage data from launch):**
- Evaluate annual pricing option
- Freemium tier tuning (is 1 system + 1 alert right?)
- Additional Pro features
- API access tiers for developer community

### Phase 4: Platform & Framework Expansion

- "Add a Transit System" contributor guide
- Template collector with documentation
- CI/CD for contributor PRs
- Community-driven transit system additions
- Framework vs. app branding may need to split eventually

### Phase 5: Sustainability (Ongoing)

**Technical debt:**
- Backend test coverage (limited for schedule generation)
- iOS test coverage
- Smarter cache invalidation
- Web app needs tests
- Move Android to separate private repo

**Governance:**
- Publish board meeting notes to repo
- Public roadmap (GitHub Projects)
- Decision log for contributors
- Contributor governance model (if community grows)

---

## What NOT to Do Right Now

1. **Don't add more transit systems** — Launch first, let contributors expand after.
2. **Don't build an Apple Watch app** — Won't move growth metrics.
3. **Don't add GraphQL** — REST API is fine.
4. **Don't add WebSocket** — 30-second polling is adequate.
5. **Don't add multi-language support** — English covers the target market.
6. **Don't frame against competitors** — We lift the whole sector.
7. **Don't keep polishing instead of launching** — The product is ready. Ship the marketing.

---

## Board Decisions on Record

| Decision | Resolution | Date |
|----------|-----------|------|
| Vision | Open-source general-purpose transit framework | 2026-02-06 |
| Competitor framing | None — encourage the sector | 2026-02-06 |
| Pricing | $2.99/month Pro, no changes | 2026-02-06 |
| License | Apache 2.0 (changed from GPL v3) | 2026-02-06 |
| Android | Excluded from public repo | 2026-02-06 |
| LIRR/Metro-North | Merge PR #368 before launch | 2026-02-06 |
| Infrastructure costs | Not a concern at this stage | 2026-02-06 |
| Governance | Public board proceedings and decision logs | 2026-02-06 |
| Pricing update | $4.99/month Pro | 2026-03-19 |
| Freemium model | 1 free system, 1 free alert; revisit after launch | 2026-03-19 |
| Track predictions | Free for all users (not paywalled) | 2026-03-19 |
| Launch sequence | Videos → ASO → repo public → Reddit → HN | 2026-03-19 |
| Defer post-launch | PWA, analytics, deep links, Android repo split | 2026-03-19 |

---

## Open Questions

1. **App Store Connect analytics:** Do we have data on impressions, conversion rate? Would help tune ASO.

2. **Active user estimate:** Can we estimate from API request logs before analytics is integrated?

3. **NJ Transit relationship risk:** Success could attract the same adversarial attention Clever Commute received. No action needed now, but worth monitoring.

4. **Post-launch priorities:** Revisit after initial reception data from Reddit/HN launch.

---

## Success Metrics (30-day targets from launch)

- App Store ratings: increase significantly from current count
- GitHub stars: establish baseline
- Reddit post engagement: 50+ upvotes on r/NJTransit
- Hacker News: front page
- Weekly downloads: increase from ~20/week baseline
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
│   │   ├── services/    # Business logic
│   │   ├── collectors/  # Data collectors (njt, amtrak, path, lirr, mnr, subway, service_alerts)
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
│   └── terraform/       # GCE MIGs, Cloud SQL, etc.
├── board-meetings/      # Public board meeting minutes
├── .github/workflows/   # CI/CD
├── .claude/             # PM tooling, rules, agents
├── CEO.md               # This file (strategic direction)
└── CLAUDE.md            # Project-wide development rules
```

### Backend Data Collection Architecture
- **NJT/Amtrak**: Multi-phase — Schedule Generation (daily) → Discovery (30min) → Collection (15min) → JIT Updates (on-demand) → Validation (hourly)
- **PATH**: Single collector every 4 minutes using native RidePATH API, discovers at all 13 stations
- **PATCO**: GTFS static schedules from SEPTA feed, no real-time API
- **LIRR/Metro-North**: Unified GTFS-RT collectors, shared logic in mta_common.py, every 4 minutes
- **NYC Subway**: Single collector processing 8 GTFS-RT feeds, 36 routes, 472 stations, shared mta_common.py logic
- **Service Alerts**: MTA GTFS-RT service alert feeds for Subway, LIRR, Metro-North; NJT via getStationMSG API

### iOS Pro Features (gated by SubscriptionService)
1. Multiple train systems (free tier: 1 system)
2. Multiple route alerts (free tier: 1 alert)
3. Live Activities (lock screen + Dynamic Island)
4. Delay Forecasts (stop-level delay/cancellation probability)
5. Live Congestion Map (interactive)
6. Historical Analytics
7. Trip History/Statistics
8. RatSense AI (journey suggestions)
9. Penn Station Boarding Guide

Note: Track predictions are free for all users (board decision 2026-03-19).

### API Environments
- Production: `https://apiv2.trackrat.net/api/v2`
- Staging: `https://staging.apiv2.trackrat.net/api/v2`
- Web app: `https://trackrat.net/`
- Landing page: `https://trackrat.net/`

### App Store Details
- App Store URL: `https://apps.apple.com/us/app/trackrat/id6746423610`
- App ID: `6746423610`
- Requires iOS 17.0+
- Developer privacy stance: "does not collect any data"

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
1. Predictions (not historical frequency)
2. Multi-system unified view (8 systems)
3. Open source (Apache 2.0)
4. Live Activities (no other transit app has this)
5. Route alerts with planned work notifications
6. Privacy-first (no data collection, verifiable via source code)
7. Built through vibe coding (unique development story)
8. Freemium model ($4.99/month vs. $50/year for Clever Commute)

---

## Appendix C: Social Channels

- YouTube: `https://www.youtube.com/@TrackRat-App/shorts`
- Instagram: `https://www.instagram.com/trackratapp/`
- Feedback portal: `https://trackrat.nolt.io/`
- Support email: `trackrat@andymartin.cc`
- GitHub: `https://github.com/bokonon1/TrackRat` (currently private, going public this week)

---

*This is a living document maintained by the CEO (Claude) and approved by the Board (Andy). Updated after each board meeting.*
