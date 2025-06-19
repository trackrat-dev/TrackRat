#!/bin/bash
# Yamllint wrapper for pre-commit to avoid complex quoting issues
yamllint -d '{extends: default, rules: {line-length: disable, document-start: disable, truthy: disable}}' .github/workflows/