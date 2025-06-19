# TrackRat Root Makefile
# Convenience commands for development and deployment

.PHONY: help deploy-dev deploy-dev-quick deploy-dev-infra deploy-dev-docker status-dev test lint clean

# Default target
help:
	@echo "TrackRat Development Commands:"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy-dev         - Full deployment (infrastructure + application)"
	@echo "  make deploy-dev-quick   - Quick app deployment (skip tests & terraform)"
	@echo "  make deploy-dev-infra   - Infrastructure only deployment"
	@echo "  make deploy-dev-docker  - Docker only deployment"
	@echo ""
	@echo "Status & Monitoring:"
	@echo "  make status-dev         - Check development environment status"
	@echo "  make logs-dev           - View recent logs from dev services"
	@echo ""
	@echo "Development:"
	@echo "  make test               - Run all tests"
	@echo "  make lint               - Run linting checks"
	@echo "  make clean              - Clean build artifacts"
	@echo ""
	@echo "Backend:"
	@echo "  make backend-test       - Run backend tests"
	@echo "  make backend-shell      - Start backend shell"
	@echo "  make backend-migrate    - Run database migrations"
	@echo ""
	@echo "Infrastructure:"
	@echo "  make infra-plan         - Plan infrastructure changes"
	@echo "  make infra-validate     - Validate Terraform configuration"

# Deployment targets
deploy-dev:
	@echo "🚀 Starting full development deployment..."
	@./deploy-dev.sh

deploy-dev-quick:
	@echo "⚡ Starting quick development deployment (app only)..."
	@./deploy-dev.sh --skip-terraform --skip-tests

deploy-dev-infra:
	@echo "🏗️  Deploying infrastructure only..."
	@./deploy-dev.sh --terraform-only

deploy-dev-docker:
	@echo "🐳 Building and deploying Docker image only..."
	@./deploy-dev.sh --docker-only

# Status and monitoring
status-dev:
	@echo "📊 Checking development environment status..."
	@if [ -f ./check-dev-status.sh ]; then \
		./check-dev-status.sh; \
	else \
		echo "Status script not found. Checking services manually..."; \
		gcloud run services list --region=us-central1 --project=trackrat-dev --filter="SERVICE:trackrat-*"; \
	fi

logs-dev:
	@echo "📜 Fetching recent logs from development services..."
	@echo "\n=== API Service Logs ===\n"
	@gcloud run logs read --service=trackrat-api-dev --region=us-central1 --project=trackrat-dev --limit=20
	@echo "\n=== Scheduler Service Logs ===\n"
	@gcloud run logs read --service=trackrat-scheduler-dev --region=us-central1 --project=trackrat-dev --limit=20

# Development commands
test: backend-test infra-validate
	@echo "✅ All tests completed"

lint:
	@echo "🔍 Running linting checks..."
	@cd backend && black --check trackcast/
	@cd backend && flake8 --ignore F541,E712,F841,E203,E711,W503,F401,W291,E501 trackcast/
	@cd infra && make format validate

clean:
	@echo "🧹 Cleaning build artifacts..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Clean complete"

# Backend specific commands
backend-test:
	@echo "🧪 Running backend tests..."
	@cd backend && pytest tests/unit/ -v --tb=short

backend-shell:
	@echo "🐚 Starting backend shell..."
	@cd backend && python -c "import trackcast; import IPython; IPython.embed()"

backend-migrate:
	@echo "🔄 Running database migrations..."
	@cd backend && trackcast init-db

# Infrastructure specific commands
infra-plan:
	@echo "📋 Planning infrastructure changes..."
	@cd infra/environments/dev && terraform plan

infra-validate:
	@echo "✔️  Validating Terraform configuration..."
	@cd infra && make test

# Docker commands
docker-build:
	@echo "🐳 Building Docker image locally..."
	@cd backend && docker build -t trackcast:local --target runtime .

docker-run:
	@echo "🏃 Running Docker container locally..."
	@cd backend && docker-compose up

# Utility commands
.PHONY: check-tools
check-tools:
	@echo "🔧 Checking required tools..."
	@command -v gcloud >/dev/null 2>&1 || { echo "❌ gcloud CLI not found"; exit 1; }
	@command -v docker >/dev/null 2>&1 || { echo "❌ Docker not found"; exit 1; }
	@command -v terraform >/dev/null 2>&1 || { echo "❌ Terraform not found"; exit 1; }
	@command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3 not found"; exit 1; }
	@echo "✅ All required tools found"

.PHONY: setup
setup: check-tools
	@echo "🔧 Setting up development environment..."
	@cd backend && pip install -e .
	@cd infra && terraform init
	@echo "✅ Setup complete"