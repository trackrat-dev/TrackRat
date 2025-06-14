#!/bin/bash

# Quick validation script for Terraform infrastructure
# This script performs basic validation that actually works

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_section() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ERRORS=0

print_section "TrackRat Infrastructure Quick Test"
print_status "Working directory: $SCRIPT_DIR"

cd "$SCRIPT_DIR"

# Test Terraform format
print_section "Checking Terraform Format"
if terraform fmt -check -recursive; then
    print_status "✅ All Terraform files are properly formatted"
else
    print_error "❌ Some Terraform files need formatting"
    ERRORS=$((ERRORS + 1))
fi

# Test root module validation
print_section "Validating Root Module"
if terraform validate; then
    print_status "✅ Root module validation passed"
else
    print_error "❌ Root module validation failed"
    ERRORS=$((ERRORS + 1))
fi

# Test environment validation
print_section "Validating Environments"
for env_dir in environments/*/; do
    if [ -d "$env_dir" ]; then
        env_name=$(basename "$env_dir")
        print_status "Checking environment: $env_name"
        
        cd "$SCRIPT_DIR/$env_dir"
        
        # Initialize without backend for validation
        if terraform init -backend=false > /dev/null 2>&1; then
            if terraform validate > /dev/null 2>&1; then
                print_status "✅ Environment $env_name validation passed"
            else
                print_error "❌ Environment $env_name validation failed"
                ERRORS=$((ERRORS + 1))
            fi
        else
            print_error "❌ Environment $env_name initialization failed"
            ERRORS=$((ERRORS + 1))
        fi
        
        cd "$SCRIPT_DIR"
    fi
done

# Test file structure
print_section "Checking File Structure"
required_files=(
    "main.tf"
    "variables.tf"
    "outputs.tf"
    "Makefile"
    "lint-and-test.sh"
    "setup-backend.sh"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        print_status "✅ Required file found: $file"
    else
        print_error "❌ Required file missing: $file"
        ERRORS=$((ERRORS + 1))
    fi
done

required_dirs=(
    "modules/vpc"
    "modules/secrets"
    "modules/artifact-registry"
    "modules/apis"
    "environments/dev"
    "environments/staging"
    "environments/prod"
)

for dir in "${required_dirs[@]}"; do
    if [ -d "$dir" ]; then
        print_status "✅ Required directory found: $dir"
    else
        print_error "❌ Required directory missing: $dir"
        ERRORS=$((ERRORS + 1))
    fi
done

# Summary
print_section "Test Summary"
if [ $ERRORS -eq 0 ]; then
    print_status "🎉 All quick tests passed!"
    exit 0
else
    print_error "💥 Tests failed with $ERRORS errors"
    exit 1
fi