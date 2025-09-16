# TrackRat 🚂

Real-time train tracking system with ML-powered track predictions for NJ Transit and Amtrak, with planned support for SEPTA, PATH, and LIRR.

## ✨ Features

### Core Functionality
- **Multi-Platform**: Native iOS app with Live Activities + Android app (in development)
- **Track Predictions**: ML models predict platform assignments with confidence levels ("Owl" system)
- **Real-Time Updates**: Live train status, delays, and journey progress with 30-second refresh
- **Multi-Transit Support**: NJ Transit and Amtrak (SEPTA, PATH, LIRR placeholders exist)
- **Station Coverage**: ~144 stations including NY Penn, Newark Penn, Trenton, Princeton Junction, Metropark, plus 44 Southeast Amtrak stations
- **Smart Consolidation**: Merges duplicate trains across data sources with conflict resolution

### Advanced Features
- **Schedule Generation**: 27-hour NJT schedules + pattern-based Amtrak predictions
- **Transit Analytics**: Real-time congestion monitoring and historical route performance
- **Journey Tracking**: Segment-by-segment transit time analysis and delay attribution
- **Arrival Forecasting**: ML-powered arrival time predictions using recent journey data
- **Live Activities**: Real-time iOS Lock Screen and Dynamic Island updates
- **RatSense AI**: Intelligent journey suggestions based on user patterns (iOS)
- **Penn Station Guide**: Interactive navigation assistance with video guides (iOS)
- **Validation System**: Hourly coverage checks ensure data completeness

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Data Sources  │     │   Cloud Run     │     │ Mobile Frontends│
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ • NJ Transit    │────▶│ • API Service   │────▶│ • iOS App       │
│ • Amtrak APIs   │     │ • Scheduler     │     │ • Android App   │
│                 │     │ • ML Models     │     │ • Live Activity │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                │
                        ┌───────▼────────┐
                        │   PostgreSQL   │
                        │   Database     │
                        └────────────────┘
                                │
                        ┌───────▼────────┐
                        │ Cloud Monitoring│
                        │ • Dashboards    │
                        │ • Metrics       │
                        │ • Alerts       │
                        └────────────────┘
```

## 🚀 Quick Start

### Backend V2 (Python/FastAPI)
```bash
cd backend_v2
poetry install

# Set up PostgreSQL database
psql -U postgres
CREATE DATABASE trackratdb;
CREATE USER trackratuser WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE trackratdb TO trackratuser;
\q

# Configure environment
cp .env.example .env
# Edit .env with your NJ Transit and Amtrak API tokens

# Run migrations and start server
poetry run alembic upgrade head
poetry run uvicorn trackrat.main:app --reload
```

### iOS App (Swift/SwiftUI)
```bash
cd ios
open TrackRat.xcodeproj
# Build and run in Xcode (Cmd+R)
```

### Android App (Kotlin/Jetpack Compose)
```bash
cd android

# Set up Java environment (macOS with Homebrew)
export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
export PATH=$JAVA_HOME/bin:$PATH

# Build debug APK
./gradlew assembleDebug -x test

# Install on device/emulator
./gradlew installDebug
```

## 💻 Development

### Prerequisites
- **Backend**: Python 3.11+, Poetry, PostgreSQL 14+
- **iOS**: macOS 14+, Xcode 15+, iOS 17.0+ deployment target
- **Android**: Android Studio, JDK 17, Android SDK 34
- **Infrastructure**: Terraform 1.0+, Google Cloud SDK

### Key Technologies
- **Backend**: FastAPI, PostgreSQL, asyncpg, APScheduler, Pydantic
- **iOS**: SwiftUI, ActivityKit, Combine, async/await
- **Android**: Kotlin, Jetpack Compose, Retrofit, Hilt, Coroutines
- **Infrastructure**: Google Cloud Run, Cloud SQL, Terraform, Docker

## 🚢 Production Deployment

### Infrastructure (Google Cloud Platform)
Managed with Terraform for staging and production environments:
- **Cloud Run**: Auto-scaling containerized services
- **Cloud SQL**: PostgreSQL 17 with private networking
- **Secret Manager**: Secure credential storage
- **Cloud Monitoring**: Executive dashboards and alerts
- **Artifact Registry**: Docker image storage with cleanup policies

### Deployment Process
```bash
cd infra
./setup-backend.sh  # First time only

# Deploy to staging
make test           # ALWAYS run tests first
make staging-plan
make staging-apply

# Deploy to production
make prod-plan
make prod-apply
```

### Key Features
- Docker containerization with APNS validation at startup
- Automated database migrations after backup restore
- Horizontal scaling with database-coordinated scheduling
- Comprehensive monitoring with 4 dashboards
- API response caching with 15-minute pre-computation

## 📚 Documentation

- **Backend V2**: [`backend_v2/CLAUDE.md`](backend_v2/CLAUDE.md) - Simplified V2 API with ~95% fewer API calls
- **iOS**: [`ios/CLAUDE.md`](ios/CLAUDE.md) - Native app with Live Activities and RatSense AI
- **Android**: [`android/CLAUDE.md`](android/CLAUDE.md) - Material Design 3 app (in development)
- **Infrastructure**: [`infra/CLAUDE.md`](infra/CLAUDE.md) - Terraform and GCP setup with monitoring
- **Project Guide**: [`CLAUDE.md`](CLAUDE.md) - Comprehensive project overview and integration

## 🛠️ Development Tools

### Makefile Commands

```bash
# Testing and Quality
make test                            # Run all tests
make lint                            # Run linting checks
make clean                           # Clean build artifacts

# Backend Development
make backend-test                    # Run backend tests (pytest)
make backend-migrate                 # Run database migrations

# Infrastructure Management (CRITICAL: Always test first!)
cd infra
make test                            # Run validation tests
make staging-plan                    # Plan staging changes
make staging-apply                   # Apply staging changes
make prod-plan                       # Plan production changes
make prod-apply                      # Apply production changes

# iOS Development
make ios-build                       # Build iOS app for simulator
make ios-test                        # Run iOS tests

# Android Development
cd android
./gradlew assembleDebug -x test      # Build debug APK
./gradlew test                       # Run unit tests

# Initial Setup
make setup                           # Setup development environment
```

## 🐛 Known Issues & Areas for Improvement

### Critical Issues

#### Backend V2
- **Schedule Duplication**: SCHEDULED records may duplicate if trains appear early
- **Pattern Detection**: Amtrak pattern analysis misses irregular services
- **Test Coverage**: Limited tests for new schedule generation features
- **Memory Usage**: Pattern analysis loads 22 days of data into memory

#### iOS App
- **Memory Leaks**: Potential retain cycles in Live Activity push subscriptions
- **Search Performance**: O(n) station search on every keystroke
- **Video Loading**: Synchronous thumbnail loading blocks UI thread
- **Test Coverage**: <10% test coverage, no SwiftLint configuration

#### Android App
- **Missing Features**: No ongoing notifications (critical for train tracking)
- **Track Button**: Non-functional "Track This Train" button
- **Model Confusion**: Duplicate models (Train/TrainV2, Progress/ProgressV2)
- **Large APK**: 18.3 MB for relatively simple app

### Performance Improvements Needed
- **Cache Invalidation**: Backend uses time-based only, needs smarter invalidation
- **Database Indexes**: Some queries could benefit from additional indexes
- **API Redundancy**: Some iOS views make duplicate network requests
- **Android Caching**: No local caching of API responses

### Feature Gaps
- **Offline Support**: No offline mode in mobile apps
- **Accessibility**: Limited VoiceOver/TalkBack support
- **Localization**: English-only, no multi-language support
- **Analytics**: No usage tracking for feature improvement

## 🚀 Roadmap

### Near Term (Next Sprint)
1. Fix Android ongoing notifications with Foreground Service
2. Implement iOS memory leak fixes
3. Add comprehensive test coverage
4. Optimize search performance

### Medium Term (1-2 Months)
1. WebSocket support for real-time updates
2. Offline mode with local caching
3. Widget support (iOS and Android)
4. Accessibility improvements

### Long Term (3-6 Months)
1. Additional transit systems (LIRR, Metro-North, SEPTA, PATH)
2. GraphQL API for efficient queries
3. Apple Watch and Wear OS apps
4. Multi-language support

## 📊 Project Status

### ✅ Production Ready
- Backend V2 API with horizontal scaling
- iOS app with Live Activities
- Infrastructure with monitoring
- NJ Transit and Amtrak integration

### 🚧 In Development
- Android app (core features complete, missing train tracking)
- Enhanced ML models for track prediction
- Advanced analytics dashboards

### 📝 Planned
- Additional transit systems
- WebSocket real-time updates
- Offline support
- Multi-platform widgets

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run linting and tests
5. Submit a pull request

See individual CLAUDE.md files for component-specific guidelines.

## 📄 License

Copyright © 2025 TrackRat Team. All rights reserved.

## 🙏 Acknowledgments

- NJ Transit and Amtrak for API access
- Open source communities for excellent tools
- Beta testers for valuable feedback
- Commuters who inspired this project
