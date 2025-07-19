#!/bin/bash
#

set -xe


# Code quality checks
poetry run black src/ tests/ --check              # Code formatting check
poetry run mypy src/                               # Type checking (strict)
poetry run ruff check src/                        # Fast linting

# tests
poetry run pytest -v
