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
│   Data Sources  │     │   Backend V2    │     │    Frontends    │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ • NJ Transit    │────▶│ • FastAPI       │────▶│ • iOS App       │
│ • Amtrak APIs   │     │ • APScheduler   │     │ • Android App   │
│                 │     │ • ML Predictions│     │ • Web App       │
└─────────────────┘     └─────────────────┘     │ • Live Activity │
                                │               └─────────────────┘
                        ┌───────▼────────┐
                        │   PostgreSQL   │
                        │   Database     │
                        └────────────────┘
                                │
                        ┌───────▼────────┐
                        │   GCP Infra    │
                        │ • Cloud Run    │
                        │ • Managed MIG  │
                        │ • Monitoring   │
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
cd infra_v2/terraform
terraform init
terraform workspace select staging  # or production

# Deploy to staging
terraform plan -var="environment=staging"
terraform apply -var="environment=staging"

# Deploy to production
terraform workspace select production
terraform plan -var="environment=production"
terraform apply -var="environment=production"
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
- **Android**: [`android/CLAUDE.md`](android/CLAUDE.md) - Material Design 3 app with map-based UI
- **Web**: [`webpage_v2/CLAUDE.md`](webpage_v2/CLAUDE.md) - Mobile-first React app with Tailwind CSS
- **Infrastructure**: [`infra_v2/README.md`](infra_v2/README.md) - Terraform and GCP setup with MIG architecture
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

# Infrastructure Management
cd infra_v2/terraform
terraform init                       # Initialize Terraform
terraform workspace select staging   # Select workspace
terraform plan -var="environment=staging"  # Plan changes
terraform apply -var="environment=staging" # Apply changes

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
- **Test Coverage**: Limited tests for new schedule generation features

#### iOS App
- **Video Loading**: Synchronous thumbnail loading blocks UI thread
- **Test Coverage**: <10% test coverage, no SwiftLint configuration

#### Android App
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
1. Fix Android "Track This Train" button functionality
2. Add comprehensive test coverage
3. Optimize video loading performance
4. Consolidate duplicate Android models

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
