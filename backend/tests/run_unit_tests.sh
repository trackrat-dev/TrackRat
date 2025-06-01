#!/bin/bash

# Script to run unit tests with proper environment configuration
# This ensures tests use SQLite in-memory database instead of PostgreSQL

# Set environment variables
export TRACKCAST_ENV=test
export TRACKCAST_CONFIG="$(pwd)/tests/test_config.yaml"

# Run the tests with proper Python path
PYTHONPATH=. pytest tests/unit/ -v

# Return the pytest exit code
exit $?