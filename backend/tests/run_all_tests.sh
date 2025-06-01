#!/bin/bash

# Exit on error
set -e

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}TrackCast Test Suite Runner${NC}"
echo -e "${YELLOW}==========================${NC}"
echo

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Run code formatting check with black
echo -e "\n${YELLOW}Running code formatting check with black...${NC}"
if black --check trackcast/; then
    echo -e "${GREEN}✓ Code formatting looks good!${NC}"
else
    echo -e "${RED}✗ Code formatting issues found. Run 'black trackcast/' to fix.${NC}"
    exit 1
fi

# Run isort check for import ordering
echo -e "\n${YELLOW}Running import ordering check with isort...${NC}"
if command -v isort &> /dev/null; then
    if isort --check-only --profile black trackcast/; then
        echo -e "${GREEN}✓ Import ordering looks good!${NC}"
    else
        echo -e "${RED}✗ Import ordering issues found. Run 'isort --profile black trackcast/' to fix.${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ isort not installed. Skipping import ordering check.${NC}"
fi

# Run linting with flake8
echo -e "\n${YELLOW}Running linting with flake8...${NC}"
if flake8 trackcast/; then
    echo -e "${GREEN}✓ No linting issues found!${NC}"
else
    echo -e "${RED}✗ Linting issues found. Please fix the issues listed above.${NC}"
    exit 1
fi

# Run type checking with mypy
echo -e "\n${YELLOW}Running type checking with mypy...${NC}"
if mypy trackcast/; then
    echo -e "${GREEN}✓ Type checking passed!${NC}"
else
    echo -e "${RED}✗ Type checking issues found. Please fix the issues listed above.${NC}"
    exit 1
fi

# Run security checks with bandit
echo -e "\n${YELLOW}Running security checks with bandit...${NC}"
if command -v bandit &> /dev/null; then
    if bandit -r trackcast/ -x tests/; then
        echo -e "${GREEN}✓ Security check passed!${NC}"
    else
        echo -e "${RED}✗ Security issues found. Please review the issues listed above.${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ bandit not installed. Skipping security check.${NC}"
fi

# Run unit tests with pytest
echo -e "\n${YELLOW}Running unit tests...${NC}"
if pytest tests/unit/ -v; then
    echo -e "${GREEN}✓ Unit tests passed!${NC}"
else
    echo -e "${RED}✗ Unit tests failed. Please fix the failing tests.${NC}"
    exit 1
fi

# Run integration tests with pytest
echo -e "\n${YELLOW}Running integration tests...${NC}"
if pytest tests/integration/ -v; then
    echo -e "${GREEN}✓ Integration tests passed!${NC}"
else
    echo -e "${RED}✗ Integration tests failed. Please fix the failing tests.${NC}"
    exit 1
fi

# Run tests with coverage report
echo -e "\n${YELLOW}Running tests with coverage report...${NC}"
if pytest --cov=trackcast --cov-report=term-missing --cov-report=html; then
    echo -e "${GREEN}✓ Coverage tests passed!${NC}"
    echo -e "HTML coverage report generated in htmlcov/ directory."
else
    echo -e "${RED}✗ Coverage tests failed. Please fix the failing tests.${NC}"
    exit 1
fi

echo -e "\n${GREEN}All tests completed successfully!${NC}"
echo -e "Open htmlcov/index.html to view the detailed coverage report."