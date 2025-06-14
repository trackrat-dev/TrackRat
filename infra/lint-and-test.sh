#!/bin/bash

# Terraform linting and testing script for TrackRat infrastructure
# This script runs comprehensive checks on all Terraform code

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_section() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

# Global variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ERRORS=0
WARNINGS=0

# Function to increment error count
increment_errors() {
    ERRORS=$((ERRORS + 1))
}

# Function to increment warning count
increment_warnings() {
    WARNINGS=$((WARNINGS + 1))
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install required tools
install_tools() {
    print_section "Installing Required Tools"
    
    # Check for Terraform
    if ! command_exists terraform; then
        print_error "Terraform is not installed. Please install it first."
        print_status "Install from: https://www.terraform.io/downloads.html"
        increment_errors
        return 1
    else
        print_status "Terraform: $(terraform version | head -n1)"
    fi
    
    # Check for tflint
    if ! command_exists tflint; then
        print_warning "tflint not found. Installing..."
        if command_exists curl; then
            curl -s https://raw.githubusercontent.com/terraform-linters/tflint/master/install_linux.sh | bash
        else
            print_error "curl not found. Please install tflint manually."
            print_status "Install from: https://github.com/terraform-linters/tflint"
            increment_errors
            return 1
        fi
    else
        print_status "tflint: $(tflint --version)"
    fi
    
    # Check for terraform-docs
    if ! command_exists terraform-docs; then
        print_warning "terraform-docs not found. Installing..."
        if command_exists go; then
            go install github.com/terraform-docs/terraform-docs@latest
        else
            print_warning "terraform-docs not available. Documentation generation will be skipped."
            increment_warnings
        fi
    else
        print_status "terraform-docs: $(terraform-docs version)"
    fi
    
    # Check for checkov (optional)
    if ! command_exists checkov; then
        print_warning "checkov not found. Security scanning will be skipped."
        print_status "Install with: pip install checkov"
        increment_warnings
    else
        print_status "checkov: $(checkov --version)"
    fi
}

# Function to format Terraform code
format_terraform() {
    print_section "Formatting Terraform Code"
    
    cd "$SCRIPT_DIR"
    
    # Format all Terraform files
    if terraform fmt -recursive -diff; then
        print_status "All Terraform files are properly formatted"
    else
        print_error "Some files were reformatted. Please commit the changes."
        increment_errors
    fi
}

# Function to validate Terraform syntax
validate_terraform() {
    print_section "Validating Terraform Syntax"
    
    local validation_errors=0
    
    # Validate root module
    cd "$SCRIPT_DIR"
    print_status "Validating root module..."
    if terraform validate; then
        print_status "Root module validation passed"
    else
        print_error "Root module validation failed"
        validation_errors=$((validation_errors + 1))
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
                validation_errors=$((validation_errors + 1))
            fi
            cd "$SCRIPT_DIR"
        fi
    done
    
    # Validate each environment
    for env_dir in environments/*/; do
        if [ -d "$env_dir" ]; then
            env_name=$(basename "$env_dir")
            print_status "Validating environment: $env_name"
            
            cd "$SCRIPT_DIR/$env_dir"
            
            # Initialize if needed (but don't connect to remote backend)
            if [ ! -d ".terraform" ]; then
                terraform init -backend=false
            fi
            
            if terraform validate; then
                print_status "Environment $env_name validation passed"
            else
                print_error "Environment $env_name validation failed"
                validation_errors=$((validation_errors + 1))
            fi
            cd "$SCRIPT_DIR"
        fi
    done
    
    if [ $validation_errors -gt 0 ]; then
        print_error "Terraform validation failed with $validation_errors errors"
        ERRORS=$((ERRORS + validation_errors))
    else
        print_status "All Terraform validation checks passed"
    fi
}

# Function to run tflint
run_tflint() {
    print_section "Running TFLint"
    
    if ! command_exists tflint; then
        print_warning "tflint not available, skipping..."
        increment_warnings
        return
    fi
    
    cd "$SCRIPT_DIR"
    
    # Initialize tflint
    tflint --init
    
    # Run tflint on root module
    print_status "Running tflint on root module..."
    if tflint --chdir=.; then
        print_status "Root module tflint passed"
    else
        print_error "Root module tflint failed"
        increment_errors
    fi
    
    # Run tflint on each module
    for module_dir in modules/*/; do
        if [ -d "$module_dir" ]; then
            module_name=$(basename "$module_dir")
            print_status "Running tflint on module: $module_name"
            
            if tflint --chdir="$module_dir"; then
                print_status "Module $module_name tflint passed"
            else
                print_error "Module $module_name tflint failed"
                increment_errors
            fi
        fi
    done
    
    # Run tflint on each environment
    for env_dir in environments/*/; do
        if [ -d "$env_dir" ]; then
            env_name=$(basename "$env_dir")
            print_status "Running tflint on environment: $env_name"
            
            if tflint --chdir="$env_dir"; then
                print_status "Environment $env_name tflint passed"
            else
                print_error "Environment $env_name tflint failed"
                increment_errors
            fi
        fi
    done
}

# Function to run security scanning with checkov
run_security_scan() {
    print_section "Running Security Scan"
    
    if ! command_exists checkov; then
        print_warning "checkov not available, skipping security scan..."
        increment_warnings
        return
    fi
    
    cd "$SCRIPT_DIR"
    
    # Run checkov on all Terraform files
    print_status "Running checkov security scan..."
    if checkov -d . --framework terraform --quiet; then
        print_status "Security scan passed"
    else
        print_error "Security scan found issues"
        increment_errors
    fi
}

# Function to generate documentation
generate_docs() {
    print_section "Generating Documentation"
    
    if ! command_exists terraform-docs; then
        print_warning "terraform-docs not available, skipping documentation generation..."
        increment_warnings
        return
    fi
    
    cd "$SCRIPT_DIR"
    
    # Generate docs for root module
    print_status "Generating documentation for root module..."
    terraform-docs markdown table --output-file README-terraform.md .
    
    # Generate docs for each module
    for module_dir in modules/*/; do
        if [ -d "$module_dir" ]; then
            module_name=$(basename "$module_dir")
            print_status "Generating documentation for module: $module_name"
            terraform-docs markdown table --output-file README.md "$module_dir"
        fi
    done
    
    print_status "Documentation generation completed"
}

# Function to run terraform plan (dry run)
run_terraform_plan() {
    print_section "Running Terraform Plan (Dry Run)"
    
    # Only run plan if explicitly requested
    if [ "$RUN_PLAN" != "true" ]; then
        print_status "Skipping terraform plan (set RUN_PLAN=true to enable)"
        return
    fi
    
    cd "$SCRIPT_DIR"
    
    # Run plan for dev environment (as example)
    if [ -d "environments/dev" ]; then
        print_status "Running terraform plan for dev environment..."
        cd environments/dev
        
        # Initialize if needed
        if [ ! -d ".terraform" ]; then
            print_warning "Terraform not initialized. Run 'terraform init' first."
            increment_warnings
            cd "$SCRIPT_DIR"
            return
        fi
        
        if terraform plan -input=false; then
            print_status "Terraform plan completed successfully"
        else
            print_error "Terraform plan failed"
            increment_errors
        fi
        
        cd "$SCRIPT_DIR"
    fi
}

# Function to print summary
print_summary() {
    print_section "Summary"
    
    if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
        print_status "All checks passed! ✅"
        exit 0
    elif [ $ERRORS -eq 0 ]; then
        print_warning "All checks passed with $WARNINGS warnings ⚠️"
        exit 0
    else
        print_error "Checks failed with $ERRORS errors and $WARNINGS warnings ❌"
        exit 1
    fi
}

# Main function
main() {
    print_status "Starting Terraform linting and testing for TrackRat"
    echo "Working directory: $SCRIPT_DIR"
    
    # Install required tools
    install_tools
    
    # Run all checks
    format_terraform
    validate_terraform
    run_tflint
    run_security_scan
    generate_docs
    run_terraform_plan
    
    # Print summary
    print_summary
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --plan)
            RUN_PLAN=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--plan] [--help]"
            echo "  --plan    Run terraform plan as part of the checks"
            echo "  --help    Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi