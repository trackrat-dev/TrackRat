# Makefile for TrackRat Infrastructure
# Provides convenient commands for linting, testing, and managing Terraform code

.PHONY: help setup lint test format validate docs security plan apply clean install-tools
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Environment variables
ENV ?= staging
TF_VAR_FILE ?= terraform.tfvars

help: ## Show this help message
	@echo "$(BLUE)TrackRat Infrastructure Commands$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ { printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""
	@echo "$(YELLOW)Environment Variables:$(NC)"
	@echo "  ENV           Environment to target (staging, prod) [default: staging]"
	@echo "  TF_VAR_FILE   Terraform variables file [default: terraform.tfvars]"
	@echo ""
	@echo "$(YELLOW)Examples:$(NC)"
	@echo "  make lint                    # Lint all Terraform code"
	@echo "  make test                    # Run all tests"
	@echo "  make plan ENV=staging        # Plan staging environment"
	@echo "  make apply ENV=prod          # Apply production environment"

install-tools: ## Install required tools (terraform, tflint, etc.)
	@echo "$(BLUE)Installing required tools...$(NC)"
	@./lint-and-test.sh --help > /dev/null 2>&1 || { echo "$(RED)Error: lint-and-test.sh not found$(NC)"; exit 1; }
	@echo "$(GREEN)Tools installation check completed$(NC)"

setup: install-tools ## Setup infrastructure backend and initialize environments
	@echo "$(BLUE)Setting up infrastructure backend...$(NC)"
	@./setup-backend.sh
	@echo "$(GREEN)Backend setup completed$(NC)"

format: ## Format all Terraform files
	@echo "$(BLUE)Formatting Terraform files...$(NC)"
	@terraform fmt -recursive
	@echo "$(GREEN)Formatting completed$(NC)"

validate: format ## Validate Terraform syntax
	@echo "$(BLUE)Validating Terraform syntax...$(NC)"
	@terraform validate
	@echo "$(GREEN)Root module validation completed$(NC)"

lint: ## Run comprehensive linting (format, validate, tflint)
	@echo "$(BLUE)Running comprehensive linting...$(NC)"
	@./lint-and-test.sh
	@echo "$(GREEN)Linting completed$(NC)"

quick-test: ## Run quick validation tests
	@echo "$(BLUE)Running quick validation tests...$(NC)"
	@./quick-test.sh
	@echo "$(GREEN)Quick tests completed$(NC)"

security: ## Run security scanning with checkov
	@echo "$(BLUE)Running security scan...$(NC)"
	@if command -v checkov >/dev/null 2>&1; then \
		checkov -d . --framework terraform --quiet; \
		echo "$(GREEN)Security scan completed$(NC)"; \
	else \
		echo "$(YELLOW)checkov not installed. Install with: pip install checkov$(NC)"; \
	fi

docs: ## Generate documentation for all modules
	@echo "$(BLUE)Generating documentation...$(NC)"
	@if command -v terraform-docs >/dev/null 2>&1; then \
		terraform-docs markdown table --output-file README-terraform.md .; \
		for dir in modules/*/; do \
			echo "Generating docs for $$dir..."; \
			terraform-docs markdown table --output-file README.md $$dir; \
		done; \
		echo "$(GREEN)Documentation generated$(NC)"; \
	else \
		echo "$(YELLOW)terraform-docs not installed. Install with: go install github.com/terraform-docs/terraform-docs@latest$(NC)"; \
	fi

test: quick-test ## Run quick tests (recommended for regular use)
	@echo "$(GREEN)Quick tests completed successfully$(NC)"

test-full: lint security docs ## Run all comprehensive tests
	@echo "$(GREEN)All comprehensive tests completed successfully$(NC)"

init: ## Initialize Terraform for specified environment
	@echo "$(BLUE)Initializing Terraform for $(ENV) environment...$(NC)"
	@if [ ! -d "environments/$(ENV)" ]; then \
		echo "$(RED)Error: Environment $(ENV) does not exist$(NC)"; \
		exit 1; \
	fi
	@cd environments/$(ENV) && terraform init
	@echo "$(GREEN)Initialization completed for $(ENV)$(NC)"

plan: init ## Plan Terraform changes for specified environment
	@echo "$(BLUE)Planning Terraform changes for $(ENV) environment...$(NC)"
	@cd environments/$(ENV) && terraform plan -var-file=$(TF_VAR_FILE)
	@echo "$(GREEN)Planning completed for $(ENV)$(NC)"

apply: init ## Apply Terraform changes for specified environment
	@echo "$(BLUE)Applying Terraform changes for $(ENV) environment...$(NC)"
	@cd environments/$(ENV) && terraform apply -var-file=$(TF_VAR_FILE)
	@echo "$(GREEN)Apply completed for $(ENV)$(NC)"

destroy: init ## Destroy Terraform infrastructure for specified environment
	@echo "$(RED)WARNING: This will destroy all infrastructure for $(ENV) environment$(NC)"
	@read -p "Are you sure? (yes/no): " confirm && [ "$$confirm" = "yes" ]
	@cd environments/$(ENV) && terraform destroy -var-file=$(TF_VAR_FILE)
	@echo "$(GREEN)Destroy completed for $(ENV)$(NC)"

output: ## Show Terraform outputs for specified environment
	@echo "$(BLUE)Showing outputs for $(ENV) environment...$(NC)"
	@cd environments/$(ENV) && terraform output
	@echo "$(GREEN)Outputs displayed for $(ENV)$(NC)"

state-list: ## List Terraform state for specified environment
	@echo "$(BLUE)Listing Terraform state for $(ENV) environment...$(NC)"
	@cd environments/$(ENV) && terraform state list
	@echo "$(GREEN)State list completed for $(ENV)$(NC)"

clean: ## Clean temporary files and .terraform directories
	@echo "$(BLUE)Cleaning temporary files...$(NC)"
	@find . -type d -name ".terraform" -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.tfplan" -delete 2>/dev/null || true
	@find . -name ".terraform.lock.hcl" -delete 2>/dev/null || true
	@echo "$(GREEN)Cleanup completed$(NC)"

pre-commit-install: ## Install pre-commit hooks
	@echo "$(BLUE)Installing pre-commit hooks...$(NC)"
	@if command -v pre-commit >/dev/null 2>&1; then \
		pre-commit install; \
		echo "$(GREEN)Pre-commit hooks installed$(NC)"; \
	else \
		echo "$(YELLOW)pre-commit not installed. Install with: pip install pre-commit$(NC)"; \
	fi

pre-commit-run: ## Run pre-commit hooks on all files
	@echo "$(BLUE)Running pre-commit hooks...$(NC)"
	@if command -v pre-commit >/dev/null 2>&1; then \
		pre-commit run --all-files; \
		echo "$(GREEN)Pre-commit hooks completed$(NC)"; \
	else \
		echo "$(YELLOW)pre-commit not installed. Install with: pip install pre-commit$(NC)"; \
	fi

# Environment-specific shortcuts
staging-plan: ## Plan staging environment
	@$(MAKE) plan ENV=staging

staging-apply: ## Apply staging environment
	@$(MAKE) apply ENV=staging

prod-plan: ## Plan production environment
	@$(MAKE) plan ENV=prod

prod-apply: ## Apply production environment
	@$(MAKE) apply ENV=prod