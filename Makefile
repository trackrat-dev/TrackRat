# TrackRat Root Makefile
# Convenience commands for development

.PHONY: help test lint clean backend-test backend-migrate infra-plan infra-validate

# Default target
help:
	@echo "TrackRat Development Commands:"
	@echo ""
	@echo "Development:"
	@echo "  make test               - Run all tests"
	@echo "  make lint               - Run linting checks"
	@echo "  make clean              - Clean build artifacts"
	@echo ""
	@echo "Backend:"
	@echo "  make backend-test       - Run backend tests"
	@echo "  make backend-migrate    - Run database migrations"
	@echo ""
	@echo "Infrastructure:"
	@echo "  make infra-plan         - Plan infrastructure changes"
	@echo "  make infra-validate     - Validate Terraform configuration"

# Development commands
test: backend-test infra-validate
	@echo "✅ All tests completed"

lint:
	@echo "🔍 Running linting checks..."
	@cd backend_v2 && poetry run black --check src/ tests/
	@cd backend_v2 && poetry run ruff check src/
	@cd backend_v2 && poetry run mypy src/
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
	@cd backend_v2 && poetry run pytest -v

backend-migrate:
	@echo "🔄 Running database migrations..."
	@cd backend_v2 && poetry run alembic upgrade head

# Infrastructure specific commands
infra-plan:
	@echo "📋 Planning infrastructure changes..."
	@cd infra/environments/staging && terraform plan

infra-validate:
	@echo "✔️  Validating Terraform configuration..."
	@cd infra && make test

# Utility commands
.PHONY: check-tools
check-tools:
	@echo "🔧 Checking required tools..."
	@command -v poetry >/dev/null 2>&1 || { echo "❌ Poetry not found"; exit 1; }
	@command -v terraform >/dev/null 2>&1 || { echo "❌ Terraform not found"; exit 1; }
	@command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3 not found"; exit 1; }
	@echo "✅ All required tools found"

.PHONY: setup
setup: check-tools
	@echo "🔧 Setting up development environment..."
	@cd backend_v2 && poetry install
	@cd infra && terraform init
	@echo "✅ Setup complete"