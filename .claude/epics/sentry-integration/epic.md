---
name: sentry-integration
status: backlog
created: 2025-09-19T00:43:48Z
progress: 0%
prd: .claude/prds/sentry-integration.md
github: https://github.com/bokonon1/TrackRat/issues/233
---

# Epic: sentry-integration

## Overview
Deploy Sentry's complete observability suite (error monitoring, session replay, distributed tracing, and profiling) across both staging and production environments for the Python FastAPI backend and iOS app. This integration will provide comprehensive visibility into system health, enabling rapid debugging and performance optimization.

## Architecture Decisions

### Key Technical Decisions
- **SaaS over Self-Hosted**: Use Sentry.io Business plan for managed infrastructure and advanced features
- **Full Feature Enablement**: Deploy all features immediately rather than phased approach
- **Environment Parity**: Same instrumentation code for staging/production, different sampling rates
- **Minimal Code Changes**: Leverage automatic instrumentation where possible (FastAPI, SQLAlchemy, httpx)
- **Existing Infrastructure**: Use current logging (structlog) and correlation IDs as foundation

### Technology Choices
- **Backend SDK**: `sentry-sdk[fastapi]>=2.0.0` with automatic integrations
- **iOS SDK**: `Sentry-Swift>=8.30.0` with SwiftUI support
- **Trace Propagation**: W3C trace context headers for distributed tracing
- **Performance Monitoring**: Native SDK profiling (no external APM needed)

### Design Patterns
- **Middleware Pattern**: Single integration point in FastAPI/iOS app initialization
- **Decorator Pattern**: Wrap critical functions with custom spans
- **Context Enrichment**: Attach business context (train IDs, stations) to all events
- **Graceful Degradation**: Continue operation if Sentry is unavailable

## Technical Approach

### Backend Components
**Integration Points**:
- FastAPI middleware in `main.py` for automatic request/response capture
- Custom context processors for train/station metadata
- Performance spans for transit API calls and database queries
- Cron monitoring for APScheduler jobs
- Structured logging integration with existing correlation IDs

**Key Files**:
- `backend_v2/src/trackrat/main.py` - SDK initialization and middleware
- `backend_v2/src/trackrat/services/scheduler.py` - Cron monitoring
- `backend_v2/src/trackrat/collectors/*/client.py` - API performance spans

### iOS Components
**Integration Points**:
- SDK initialization in `TrackRatApp.swift` with all features enabled
- Automatic UIViewController and network tracking
- Custom breadcrumbs for Live Activity lifecycle
- User context with selected stations and environment
- Session replay with privacy controls

**Key Files**:
- `iOS/TrackRat/App/TrackRatApp.swift` - SDK initialization
- `iOS/TrackRat/Services/APIService.swift` - Network spans
- `iOS/TrackRat/Services/LiveActivityService.swift` - Live Activity tracking

### Infrastructure
**Configuration Management**:
- Environment variables for backend (Cloud Run)
- Info.plist configuration for iOS
- Separate DSNs for staging/production
- GitHub Actions for release tracking and symbol uploads

**No Additional Infrastructure Required**:
- Use existing Cloud Run deployments
- Leverage current CI/CD pipelines
- No new monitoring infrastructure needed

## Implementation Strategy

### Development Phases
1. **Setup & Configuration** (Day 1 Morning)
   - Create Sentry organization and projects
   - Configure environments and DSNs
   - Set up initial alert rules

2. **Backend Integration** (Day 1 Afternoon)
   - Add SDK with automatic instrumentation
   - Configure custom context and tags
   - Deploy to staging, then production

3. **iOS Integration** (Day 1-2)
   - Integrate SDK with all features
   - Configure session replay consent
   - Submit TestFlight and App Store builds

4. **Optimization** (Day 2-3)
   - Fine-tune sampling rates
   - Create dashboards
   - Document patterns

### Risk Mitigation
- **Performance Impact**: Monitor overhead, disable features if >5% degradation
- **Quota Management**: Dynamic sampling with spike protection
- **Privacy**: PII scrubbing rules and user consent for replay

### Testing Approach
- **Staging First**: Full testing in staging with 100% sampling
- **Synthetic Errors**: Generate test errors to verify capture
- **Performance Validation**: Measure SDK overhead with profiling

## Task Breakdown Preview

High-level implementation tasks (keeping it simple and focused):

- [ ] **Sentry Setup**: Create organization, projects, configure environments and team access
- [ ] **Backend SDK Integration**: Add sentry-sdk to FastAPI with automatic instrumentation
- [ ] **Backend Context Enhancement**: Add custom tags, user context, and cron monitoring
- [ ] **iOS SDK Integration**: Add Sentry-Swift with error, tracing, replay, and profiling
- [ ] **iOS Context Enhancement**: Configure breadcrumbs, user context, and Live Activity tracking
- [ ] **CI/CD Updates**: Configure release tracking, source maps, and dSYM uploads
- [ ] **Monitoring Configuration**: Set up alerts, dashboards, and issue assignment rules
- [ ] **Documentation**: Create runbooks for common issues and team onboarding

## Dependencies

### External Dependencies
- Sentry.io Business plan subscription
- Apple Developer account for dSYM uploads
- GitHub Actions for CI/CD integration

### Internal Dependencies
- DevOps team for environment variable configuration
- No code dependencies - can proceed immediately

### Prerequisite Work
- None - can begin immediately with current codebase

## Success Criteria (Technical)

### Performance Benchmarks
- SDK overhead <5% for both platforms
- Error capture latency <50ms
- Complete trace visibility for 20% of production requests

### Quality Gates
- 100% of unhandled exceptions captured
- All APScheduler jobs monitored
- Session replay working on 30% of iOS sessions

### Acceptance Criteria
- Staging and production fully instrumented
- Custom dashboards created for key metrics
- Team trained on Sentry usage
- Runbooks documented for common issues

## Estimated Effort

### Overall Timeline
- **Total Duration**: 3 days
- **Team Required**: 1 backend developer, 1 iOS developer
- **Complexity**: Low - mostly configuration and integration

### Resource Requirements
- Backend Developer: 1 day for integration and testing
- iOS Developer: 1.5 days for integration and App Store submission
- DevOps: 2 hours for environment configuration

### Critical Path Items
1. Sentry account setup (blocker for everything)
2. Backend deployment (can parallel with iOS)
3. iOS App Store submission (longest lead time)

## Simplification Opportunities

### Leveraging Existing Features
- Use automatic instrumentation instead of manual spans where possible
- Leverage existing correlation IDs and structured logging
- Reuse current error handling patterns with Sentry capture

### Avoiding Over-Engineering
- No custom Sentry UI or dashboards initially
- Use default grouping rules before customization
- Start with simple alert rules, refine based on experience
- No integration with external tools (Jira, Slack) initially

## Tasks Created

- [ ] #234 - Complete Backend Sentry Configuration (parallel: true)
- [ ] #235 - Add Backend Custom Instrumentation (parallel: false, depends on #234)
- [ ] #236 - Backend Testing and Deployment (parallel: false, depends on #235)
- [ ] #237 - iOS Sentry SDK Integration (parallel: true)
- [ ] #238 - iOS Custom Instrumentation and Context (parallel: false, depends on #237)
- [ ] #239 - iOS Testing and App Store Submission (parallel: false, depends on #238)
- [ ] #240 - CI/CD and Release Management Setup (parallel: true, depends on #236, #239)
- [ ] #241 - Monitoring and Alert Configuration (parallel: true, depends on #236, #239)

Total tasks: 8
Parallel tasks: 3 (#234, #237 can start immediately; #240, #241 can run together)
Sequential tasks: 5
Estimated total effort: ~35 hours (backend: 14-20h, iOS: 16-22h, DevOps: 4-6h)
