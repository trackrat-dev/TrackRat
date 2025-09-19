---
name: sentry-integration
description: Comprehensive error monitoring and performance tracking integration with Sentry for TrackRat backend and iOS app
status: backlog
created: 2025-09-18T23:59:30Z
---

# PRD: sentry-integration

## Executive Summary

Immediately deploy Sentry's complete observability suite across TrackRat's production and staging environments, leveraging error monitoring, session replay, distributed tracing, and continuous profiling for both the Python FastAPI backend and iOS app. This comprehensive integration will provide real-time visibility into transit API reliability, Live Activity tracking, background scheduler monitoring, and performance bottlenecks, enabling rapid debugging and optimization of the entire system.

## Problem Statement

TrackRat's production environment faces specific observability challenges:
- **Transit API Failures**: NJ Transit and Amtrak APIs frequently timeout or return errors, impacting train discovery and journey updates
- **Live Activity Issues**: Background refresh failures and push notification delivery problems go undetected
- **Scheduler Reliability**: The APScheduler running discovery/collection tasks lacks monitoring for job failures and performance
- **Database Performance**: PostgreSQL connection pool exhaustion and slow queries during peak hours
- **iOS Crashes**: Decoding errors from API changes and Live Activity state management issues
- **Performance Bottlenecks**: Congestion calculation endpoints taking >500ms, impacting user experience

Without Sentry, debugging relies on CloudWatch logs and user reports, resulting in slow MTTR and poor user experience during service disruptions.

## User Stories

### Primary User Personas

**1. DevOps Engineer**
- As a DevOps engineer, I want to receive immediate alerts when error rates spike so I can respond before users are impacted
- As a DevOps engineer, I want to see error patterns across different environments so I can prevent issues from reaching production
- As a DevOps engineer, I want performance metrics to identify bottlenecks in API response times

**2. Backend Developer**
- As a backend developer, I want detailed error context with stack traces so I can quickly reproduce and fix bugs
- As a backend developer, I want to track custom events for train data processing failures
- As a backend developer, I want to see database query performance to optimize slow endpoints

**3. iOS Developer**
- As an iOS developer, I want crash reports with device context so I can prioritize fixes for most-affected users
- As an iOS developer, I want breadcrumb trails showing user actions before crashes
- As an iOS developer, I want to track app launch times and screen load performance

**4. Product Manager**
- As a product manager, I want error impact metrics to prioritize feature development vs. bug fixes
- As a product manager, I want release health dashboards to make informed rollback decisions
- As a product manager, I want user feedback linked to error reports for better context

## Requirements

### Functional Requirements

**Backend Integration (Python/FastAPI)**
- **Error Capture**:
  - Transit API failures (NJT `getDepartureVisionData`, Amtrak station APIs)
  - Database connection pool exhaustion and query timeouts
  - APNS delivery failures for Live Activities
  - Schedule generation and pattern analysis errors
- **Performance Monitoring**:
  - API endpoint latency (target <100ms p95)
  - External API response times (NJT, Amtrak)
  - Database query performance (complex joins in departure service)
  - Background job duration (discovery, collection, validation)
- **Custom Context**:
  - Train ID, journey date, station codes
  - Data source (NJT/AMTRAK)
  - Scheduler task names and run IDs
  - Cloud Run revision ID for horizontal scaling
- **Cron Monitoring**: APScheduler job execution tracking

**iOS App Integration**
- **Crash Reporting**:
  - Live Activity state management crashes
  - JSON decoding errors from API changes
  - Background task completion failures
  - Navigation stack corruption
- **Performance Monitoring**:
  - Screen load times (TrainListView, TrainDetailsView)
  - API call durations and timeout tracking
  - Live Activity update latency
  - Journey progress calculation performance
- **User Context**:
  - Selected origin/destination stations
  - Active Live Activities count
  - Server environment (prod/staging/dev)
  - Recent trip history
- **Breadcrumbs**:
  - Navigation flow through station pickers
  - Live Activity start/stop events
  - Background refresh triggers
  - Push notification interactions

**Cross-Platform Features**
- **Distributed Tracing**: Complete request flow from iOS → Backend → Transit APIs with trace propagation
- **Session Replay** (iOS): Visual reproduction of user sessions leading to errors
- **Continuous Profiling**: CPU, memory, and I/O profiling for both platforms
- **Custom Tags**:
  - `train.id`, `train.line`, `station.origin`, `station.destination`
  - `datasource` (NJT/AMTRAK), `journey.date`
  - `environment` (production, staging)
  - `feature` (live_activity, scheduler, api_cache)
- **Error Grouping**: By error type, API endpoint, train line
- **Sampling Strategy**:
  - Errors: 100% capture
  - Transactions: 20% in production, 100% in staging
  - Profiling: 10% in production, 50% in staging
  - Session Replay: 30% in production, 100% in staging

### Non-Functional Requirements

**Performance**
- Error reporting must not add >50ms latency to API requests
- iOS SDK must not increase app launch time by >100ms
- Background error transmission to avoid blocking user interactions
- Batch error reporting to minimize network overhead

**Security**
- No PII (email, phone numbers) in error reports
- Encrypted transmission of all error data
- Secure storage of Sentry DSN and API keys
- IP address anonymization
- Configurable data retention (30-90 days)

**Scalability**
- Support for 100k+ daily active users
- Handle burst error rates during service disruptions
- Automatic error sampling when limits approached
- Queue-based error submission with retry logic

**Reliability**
- Graceful degradation if Sentry is unavailable
- Local error caching for offline scenarios
- Configurable timeout for Sentry API calls
- Circuit breaker pattern for Sentry connectivity

## Success Criteria

### Key Metrics
- **Error Detection Rate**: 100% of unhandled exceptions captured
- **Transit API Monitoring**: Track success rate per endpoint (target >95%)
- **Live Activity Health**: Monitor successful update rate (target >98%)
- **Scheduler Reliability**: Job success rate tracking (target >99%)
- **Performance Targets**:
  - Backend API p95 latency <100ms
  - iOS screen load time <500ms
  - Background refresh completion <5s
- **MTTR Improvement**: From ~2 hours to <30 minutes for critical issues

### Measurable Outcomes
- **Week 1**: 100% error visibility across both environments
- **Week 2**: 50% reduction in MTTR through session replay and tracing
- **Month 1**: 90% of performance bottlenecks identified via profiling
- **Month 2**: 75% reduction in debugging time with full context
- **Month 3**: Zero undetected service outages lasting >5 minutes
- **Ongoing**: Maintain 99.5% crash-free rate for iOS app

## Constraints & Assumptions

### Constraints
- Sentry Business plan required for session replay and profiling features
- iOS app size increase ~3-4MB with full SDK features
- Backend memory overhead ~75MB with profiling enabled
- Must maintain GDPR compliance for EU users
- Session replay requires user consent on iOS

### Assumptions
- Immediate rollout to both production and staging environments
- Full feature enablement (error monitoring, replay, tracing, profiling)
- Development team will receive Sentry training during rollout
- Users will be prompted for session replay consent on iOS
- Sufficient Sentry quota for comprehensive monitoring

## Out of Scope

The following items are explicitly NOT included in this integration:
- Custom Sentry self-hosted deployment (using Sentry.io SaaS)
- Session replay or screen recording features
- User feedback forms within the app
- Integration with external ticketing systems (Jira, Linear)
- Custom Sentry UI development
- Profiling or APM beyond basic performance monitoring
- Log aggregation from infrastructure components
- A/B testing or feature flag integration
- Revenue impact tracking
- Marketing analytics or user behavior tracking
- Development environment monitoring (only staging/production)
- Android app integration (iOS only currently)
- Self-hosted Sentry deployment

## Dependencies

### External Dependencies
- **Sentry.io Business Plan**: Required for session replay and profiling features
- **Apple App Store**: Approval for SDK integration with session replay
- **GitHub Actions**: For release tracking, source maps, and dSYM uploads
- **Cloud Run**: Environment variable configuration for staging/production

### Internal Team Dependencies
- **DevOps Team**:
  - Configure Sentry projects and environments
  - Set up alerting rules and notification channels
  - Manage API keys and DSN configuration

- **Backend Team**:
  - Implement Python SDK integration
  - Add custom context for train-specific errors
  - Update CI/CD for release tracking

- **iOS Team**:
  - Integrate Swift SDK
  - Configure symbolication and dSYM uploads
  - Implement breadcrumb tracking

- **Security Team**:
  - Review and approve data sanitization rules
  - Validate GDPR compliance measures
  - Approve SDK security assessment

### Technical Dependencies
- Python 3.11+ for backend SDK compatibility
- iOS 14+ for full SDK feature support
- FastAPI 0.100+ for middleware integration
- Xcode 15+ for debug symbol processing

## Implementation Details

### Backend-Specific Implementation

**Key Integration Points**:
1. **FastAPI Middleware** (`main.py`):
   - Add Sentry ASGI middleware after correlation ID middleware
   - Capture request/response with custom context
   - Integrate with existing structlog setup

2. **Transit API Collectors** (`collectors/njt/`, `collectors/amtrak/`):
   - Wrap API calls with performance spans
   - Custom error types for different failure modes
   - Retry tracking and timeout monitoring

3. **Scheduler Service** (`services/scheduler.py`):
   - Cron check-ins for each job type
   - Performance tracking for discovery/collection phases
   - Error context with last successful run times

4. **Database Operations** (`db/`):
   - Query performance monitoring
   - Connection pool metrics
   - Slow query identification

5. **Key Files to Instrument**:
   - `main.py` - Application lifecycle
   - `services/departure.py` - Complex queries and JIT updates
   - `services/scheduler.py` - Background jobs
   - `collectors/*/client.py` - External API calls
   - `services/apns.py` - Push notifications

### iOS-Specific Implementation

**Key Integration Points**:
1. **App Lifecycle** (`TrackRatApp.swift`):
   - Initialize Sentry in app launch
   - Scene phase tracking
   - Background task monitoring

2. **API Service** (`Services/APIService.swift`):
   - Network request spans
   - Error context with endpoints
   - Response time tracking

3. **Live Activities** (`Services/LiveActivityService.swift`):
   - Activity start/stop tracking
   - Background update performance
   - Push notification handling

4. **Navigation** (`AppState.swift`):
   - Breadcrumb tracking
   - View appearance events
   - User interaction tracking

5. **Key Files to Instrument**:
   - `TrackRatApp.swift` - App initialization
   - `APIService.swift` - Network layer
   - `LiveActivityService.swift` - Live Activity management
   - `TrainListView.swift` - Main list performance
   - `TrainDetailsView.swift` - Detail view loading

### Configuration

**Environment Variables (Backend)**:
```python
# Production
SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.2
SENTRY_PROFILES_SAMPLE_RATE=0.1
SENTRY_ENABLE_TRACING=true

# Staging
SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx
SENTRY_ENVIRONMENT=staging
SENTRY_TRACES_SAMPLE_RATE=1.0
SENTRY_PROFILES_SAMPLE_RATE=0.5
SENTRY_ENABLE_TRACING=true
```

**iOS Configuration**:
```swift
// In TrackRatApp.swift
SentrySDK.start { options in
    options.dsn = "https://xxx@xxx.ingest.sentry.io/xxx"
    options.environment = Bundle.main.object(forInfoDictionaryKey: "SENTRY_ENVIRONMENT") as? String ?? "production"

    // Error Monitoring
    options.enableCaptureFailedRequests = true

    // Session Replay
    options.experimental.sessionReplay = SentryReplayOptions(sessionSampleRate: 0.3, errorSampleRate: 1.0)
    options.experimental.sessionReplay.redactAllText = false
    options.experimental.sessionReplay.redactAllImages = false

    // Tracing
    options.enableTracing = true
    options.tracesSampleRate = options.environment == "staging" ? 1.0 : 0.2
    options.enableNetworkTracking = true
    options.enableFileIOTracking = true
    options.enableCoreDataTracking = true
    options.enableAutoBreadcrumbTracking = true

    // Profiling
    options.profilesSampleRate = options.environment == "staging" ? 0.5 : 0.1
    options.enableAppHangTracking = true
    options.appHangTimeoutInterval = 2.0

    // Performance
    options.enableAutoPerformanceTracking = true
    options.enableUIViewControllerTracking = true
    options.enableNetworkBreadcrumbs = true
    options.enableSwizzling = true
    options.enableAutoBreadcrumbTracking = true
}
```

## Rollout Strategy

### Immediate Deployment Plan

**Day 1 - Backend Deployment**:
1. Deploy to staging environment with 100% sampling
2. Verify all integrations working correctly
3. Deploy to production with optimized sampling rates
4. Configure alert rules and notification channels

**Day 1 - iOS Deployment**:
1. Release TestFlight build with full Sentry integration
2. Test session replay and profiling features
3. Submit production build to App Store
4. Monitor crash-free rate and performance metrics

**Day 2-3 - Optimization**:
1. Fine-tune sampling rates based on quota usage
2. Create custom dashboards for key metrics
3. Set up team alerts and on-call rotations
4. Document common error patterns

### Risk Mitigation

1. **Quota Management**:
   - Monitor usage hourly during rollout
   - Implement dynamic sampling if approaching limits
   - Use Sentry's spike protection

2. **Performance Impact**:
   - Monitor app performance metrics
   - Disable profiling if >5% overhead
   - Use background thread for Sentry operations

3. **Privacy Compliance**:
   - Implement PII scrubbing rules
   - Request user consent for session replay
   - Configure data retention policies

4. **Alert Management**:
   - Start with critical alerts only
   - Use issue ownership rules
   - Implement alert digests for non-critical issues

## Appendix

### Technical Specifications

**SDK Versions**:
- Python: `sentry-sdk[fastapi]>=2.0.0`
- iOS: `Sentry-Swift>=8.30.0`

**Sentry Features - Full Deployment**:

**Error Monitoring** (Both Platforms):
- Unhandled exception capture with full stack traces
- Custom error types with business context
- Error grouping by fingerprint rules
- Intelligent alerting with severity levels

**Session Replay** (iOS):
- Visual replay of user sessions before crashes
- Touch interactions and navigation tracking
- Network request timeline overlay
- Privacy controls for sensitive data
- 30% sampling in production, 100% in staging

**Distributed Tracing** (Both Platforms):
- End-to-end request tracing across services
- Automatic trace propagation via headers
- Performance bottleneck identification
- Database query performance tracking
- External API latency monitoring
- Custom spans for business logic

**Continuous Profiling** (Both Platforms):
- CPU profiling for hot code paths
- Memory profiling for leak detection
- I/O profiling for blocking operations
- Differential flamegraphs between releases
- Automatic profile collection on slow transactions

**Backend-Specific**:
- Cron Monitoring for APScheduler jobs
- Database connection pool metrics
- AsyncIO event loop monitoring
- Custom metrics for transit API success rates

**iOS-Specific**:
- App hang detection (>2 second freezes)
- View controller performance tracking
- Core Data query monitoring
- Network request waterfalls
- Energy impact profiling

**Integrations**:
- FastAPI (automatic instrumentation)
- SQLAlchemy (query performance)
- httpx (external API tracking)
- structlog (log correlation)
- APScheduler (cron monitoring)

### Configuration Templates
- Backend DSN format: https://[key]@[org].ingest.sentry.io/[project]
- iOS Info.plist keys required
- Environment variable naming conventions
- Recommended performance transaction sampling rates