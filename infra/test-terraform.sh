#!/bin/bash

# Quick test script for Terraform infrastructure
# This script performs basic validation without requiring GCP authentication

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

# Function to increment error count
increment_errors() {
    ERRORS=$((ERRORS + 1))
}

# Test Terraform formatting
test_format() {
    print_section "Testing Terraform Format"
    
    cd "$SCRIPT_DIR"
    
    if terraform fmt -check -recursive; then
        print_status "All Terraform files are properly formatted"
    else
        print_error "Some Terraform files need formatting"
        increment_errors
    fi
}

# Test Terraform validation
test_validate() {
    print_section "Testing Terraform Validation"
    
    cd "$SCRIPT_DIR"
    
    # Validate root module
    print_status "Validating root module..."
    if terraform validate; then
        print_status "Root module validation passed"
    else
        print_error "Root module validation failed"
        increment_errors
    fi
    
    # Validate each module
    for module_dir in modules/*/; do
        if [ -d "$module_dir" ]; then
            module_name=$(basename "$module_dir")
            print_status "Validating module: $module_name"
            
            cd "$SCRIPT_DIR/$module_dir"
            if terraform validate; then
                print_status "Module $module_name validation passed"
            else
                print_error "Module $module_name validation failed"
                increment_errors
            fi
            cd "$SCRIPT_DIR"
        fi
    done
    
    # Validate each environment (without backend)
    for env_dir in environments/*/; do
        if [ -d "$env_dir" ]; then
            env_name=$(basename "$env_dir")
            print_status "Validating environment: $env_name"
            
            cd "$SCRIPT_DIR/$env_dir"
            
            # Initialize without backend for validation
            if terraform init -backend=false; then
                if terraform validate; then
                    print_status "Environment $env_name validation passed"
                else
                    print_error "Environment $env_name validation failed"
                    increment_errors
                fi
            else
                print_error "Environment $env_name initialization failed"
                increment_errors
            fi
            
            cd "$SCRIPT_DIR"
        fi
    done
}

# Test file structure
test_structure() {
    print_section "Testing File Structure"
    
    cd "$SCRIPT_DIR"
    
    # Check required files exist
    required_files=(
        "main.tf"
        "variables.tf"
        "outputs.tf"
        ".tflint.hcl"
        "lint-and-test.sh"
        "setup-backend.sh"
        "Makefile"
    )
    
    for file in "${required_files[@]}"; do
        if [ -f "$file" ]; then
            print_status "Required file found: $file"
        else
            print_error "Required file missing: $file"
            increment_errors
        fi
    done
    
    # Check required directories exist
    required_dirs=(
        "modules/vpc"
        "modules/secrets"
        "modules/artifact-registry"
        "modules/apis"
        "environments/staging"
        "environments/prod"
    )
    
    for dir in "${required_dirs[@]}"; do
        if [ -d "$dir" ]; then
            print_status "Required directory found: $dir"
        else
            print_error "Required directory missing: $dir"
            increment_errors
        fi
    done
    
    # Check each module has required files
    for module_dir in modules/*/; do
        if [ -d "$module_dir" ]; then
            module_name=$(basename "$module_dir")
            
            for tf_file in "main.tf" "variables.tf" "outputs.tf"; do
                if [ -f "$module_dir/$tf_file" ]; then
                    print_status "Module $module_name has $tf_file"
                else
                    print_error "Module $module_name missing $tf_file"
                    increment_errors
                fi
            done
        fi
    done
}

# Test variable consistency
test_variables() {
    print_section "Testing Variable Consistency"
    
    cd "$SCRIPT_DIR"
    
    # Check that modules are properly called with required variables
    # This is a basic check - more sophisticated validation could be added
    
    if grep -q "module.*vpc" main.tf; then
        print_status "VPC module is called in main.tf"
    else
        print_error "VPC module not found in main.tf"
        increment_errors
    fi
    
    if grep -q "module.*secrets" main.tf; then
        print_status "Secrets module is called in main.tf"
    else
        print_error "Secrets module not found in main.tf"
        increment_errors
    fi
    
    if grep -q "module.*artifact_registry" main.tf; then
        print_status "Artifact Registry module is called in main.tf"
    else
        print_error "Artifact Registry module not found in main.tf"
        increment_errors
    fi
    
    if grep -q "module.*apis" main.tf; then
        print_status "APIs module is called in main.tf"
    else
        print_error "APIs module not found in main.tf"
        increment_errors
    fi
}

# Main function
main() {
    print_status "Starting Terraform infrastructure tests"
    print_status "Working directory: $SCRIPT_DIR"
    
    # Run all tests
    test_structure
    test_format
    test_validate
    test_variables
    
    # Print summary
    print_section "Test Summary"
    
    if [ $ERRORS -eq 0 ]; then
        print_status "All tests passed! ✅"
        exit 0
    else
        print_error "Tests failed with $ERRORS errors ❌"
        exit 1
    fi
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
