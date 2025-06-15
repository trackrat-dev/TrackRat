# CI/CD Workflow Migration Guide

This document outlines the migration from separate CI and deployment workflows to the new consolidated CI/CD pipeline.

## Overview

The new `ci-cd.yml` workflow consolidates the previous `ci.yml` and `deploy-dev-unified.yml` workflows into a single, atomic pipeline that ensures deployment only occurs after all tests pass.

## Key Changes

### 1. Single Workflow File
- **Before**: Two separate workflows (`ci.yml` and `deploy-dev-unified.yml`)
- **After**: One unified workflow (`ci-cd.yml`)

### 2. Guaranteed Test Success
- **Before**: Deployment could run even if CI tests failed (race conditions)
- **After**: Deployment physically blocked until all tests pass

### 3. Docker Image Reuse
- **Before**: Docker image built twice (once in CI, once in deployment)
- **After**: Docker image built once during testing, reused for deployment

### 4. Simplified Backend Testing
- **Before**: Three parallel matrix jobs (unit, integration, docker)
- **After**: Single sequential job with all tests, reducing resource usage by ~50%

## Migration Steps

### Phase 1: Initial Setup (Current)
1. ✅ Created new `ci-cd.yml` workflow
2. ✅ Validated YAML syntax
3. ✅ Created this migration documentation
4. 🔄 Keep old workflows available but disabled

### Phase 2: Testing
1. Test new workflow in a feature branch:
   ```bash
   git checkout -b test-consolidated-ci-cd
   git add .github/workflows/ci-cd.yml
   git commit -m "test: consolidated CI/CD workflow"
   git push origin test-consolidated-ci-cd
   ```

2. Create a PR to trigger the workflow and verify:
   - All tests run correctly
   - Deployment gate logic works as expected
   - No deployment occurs on feature branches

3. Test deployment scenario:
   - Merge test PR to main
   - Verify deployment executes successfully
   - Confirm Docker image artifact is used

### Phase 3: Rollout
1. Disable old workflows temporarily:
   ```yaml
   # Add to top of ci.yml and deploy-dev-unified.yml
   name: CI Pipeline (DISABLED - See ci-cd.yml)
   on:
     workflow_dispatch:  # Only manual trigger
   ```

2. Monitor new workflow for 1-2 weeks

3. If issues arise, can quickly re-enable old workflows

### Phase 4: Cleanup
1. After successful validation period:
   - Delete `ci.yml`
   - Delete `deploy-dev-unified.yml`
   - Remove this migration guide

## Workflow Comparison

### Execution Time
- **Old**: ~5-8 minutes each workflow (10-16 minutes total)
- **New**: ~10-15 minutes total (runs sequentially but more efficient)

### Resource Usage
- **Old**: 3 backend test runners + deployment runner
- **New**: 1 backend test runner + deployment runner (50% reduction)

### Visibility
- **Old**: Two separate workflow runs to track
- **New**: Single workflow with clear phase progression

## Rollback Plan

If issues occur during migration:

1. **Quick Rollback**:
   ```bash
   # Re-enable old workflows by removing workflow_dispatch restriction
   git revert <commit-that-disabled-old-workflows>
   ```

2. **Disable new workflow**:
   ```yaml
   # Add to ci-cd.yml temporarily
   on:
     workflow_dispatch:  # Only manual trigger
   ```

3. **Investigation**:
   - Review workflow logs
   - Check deployment gate logic
   - Verify Docker artifact handling

## Benefits Summary

1. **Safety**: Deployment cannot occur without passing tests
2. **Efficiency**: 50% reduction in CI resource usage
3. **Simplicity**: Single workflow to maintain and monitor
4. **Reliability**: No race conditions between workflows
5. **Consistency**: Same Docker image tested and deployed

## Notes for Developers

- PR builds will run all applicable tests but never deploy
- Only pushes to `main` branch can trigger deployment
- iOS tests still only run when iOS code changes
- Infrastructure tests still only run when infra code changes
- Backend tests always run when backend code changes

## Questions?

If you have questions about the new workflow:
1. Check the workflow file comments
2. Review this migration guide
3. Check GitHub Actions documentation
4. Ask in team chat