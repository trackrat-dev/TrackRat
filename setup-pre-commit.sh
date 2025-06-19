#!/bin/bash
# Setup script for pre-commit hooks

echo "🔧 Setting up pre-commit hooks for TrackRat..."

# Check if pre-commit is installed
if ! command -v pre-commit &> /dev/null; then
    echo "📦 Installing pre-commit..."
    pip install pre-commit
fi

# Check if yamllint is installed (needed for workflow validation)
if ! command -v yamllint &> /dev/null; then
    echo "📦 Installing yamllint..."
    pip install yamllint
fi

# Install the pre-commit hooks
echo "🪝 Installing pre-commit hooks..."
pre-commit install
pre-commit install --hook-type pre-push

echo "✅ Pre-commit hooks installed successfully!"
echo ""
echo "📝 Hook Configuration:"
echo "  - Terraform format/validate: Runs on every commit for infra/*.tf files"
echo "  - Workflow validation: Runs on every commit for .github/workflows/*.yml files"
echo "  - Backend all tests: Runs on push for backend/*.py files"
echo ""
echo "🚀 To run all hooks manually: pre-commit run --all-files"
echo "🔍 To run specific hook: pre-commit run <hook-id>"
echo "📖 Hook IDs: backend-all-tests, terraform-fmt, terraform-validate, validate-workflows"