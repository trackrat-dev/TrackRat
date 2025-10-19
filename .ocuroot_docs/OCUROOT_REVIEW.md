# Ocuroot Implementation Review

**Review Date:** October 19, 2025
**Reviewer:** Claude Code
**Implementation Status:** Production-ready for staging, requires fixes for production

---

## Executive Summary

The Ocuroot implementation is **mostly correct** with several critical issues that need to be addressed:

- ✅ **Installation fixed**: Proper tar.gz extraction now working
- ✅ **File structure correct**: All `.ocu.star` files follow proper patterns
- ❌ **Critical CI/CD bug**: Version inputs reference non-existent step outputs
- ⚠️ **Missing state configuration**: No `store.set()` or `remotes()` configuration
- ⚠️ **Task registration issues**: Using `task()` instead of `work=[]` pattern
- ⚠️ **Missing input declarations**: Build function parameters not properly declared
- ⚠️ **Docker build location**: Build runs in CI, not in Ocuroot phase

---

## Critical Issues (Must Fix)

### 1. Missing Version Step Outputs

**File:** `.github/workflows/ci-cd.yml:438-441` (staging) and `:370-373` (production)

**Problem:**
```yaml
OCUROOT_INPUT_year: ${{ steps.version.outputs.year }}
OCUROOT_INPUT_month: ${{ steps.version.outputs.month }}
OCUROOT_INPUT_day: ${{ steps.version.outputs.day }}
OCUROOT_INPUT_sha: ${{ github.sha }}
```

**Issue:** References `steps.version.outputs.*` but there is no step with id `version` that creates these outputs. The version is created in line 156 as `$VERSION` environment variable.

**Impact:** Ocuroot deployments will fail with missing input errors.

**Fix:**

```yaml
# Option 1: Create version parsing step
- name: Parse version components
  id: version
  run: |
    echo "year=$(date -u +%Y)" >> $GITHUB_OUTPUT
    echo "month=$(date -u +%m)" >> $GITHUB_OUTPUT
    echo "day=$(date -u +%d)" >> $GITHUB_OUTPUT

# Then use the existing INPUT references
OCUROOT_INPUT_year: ${{ steps.version.outputs.year }}
OCUROOT_INPUT_month: ${{ steps.version.outputs.month }}
OCUROOT_INPUT_day: ${{ steps.version.outputs.day }}

# Option 2: Remove inputs and let build() function determine
# Remove all OCUROOT_INPUT_year/month/day and rely on build() defaults
```

**Recommended:** Option 2 is simpler since `build()` already has fallback logic for date components (lines 32-37).

---

### 2. Missing State and Remote Configuration

**File:** `backend_v2/release.ocu.star`, `environments/release.ocu.star`

**Problem:** No `store.set()` or `remotes()` configuration in any `.ocu.star` files.

**Issue:** Ocuroot doesn't know where to store state or how to authenticate to Git.

**Current behavior:** Defaults to local filesystem state (`.store/` directory).

**Impact:**
- State not shared between CI runs
- No team collaboration on state
- No Git-based state tracking

**Fix:**

Add to **both** `backend_v2/release.ocu.star` and `environments/release.ocu.star`:

```python
ocuroot("0.3.0")

# Configure Git-based state storage
def get_repo_url():
    """Get repository URL with authentication for CI"""
    env_vars = env()

    # In CI: use https with token
    if "GH_TOKEN" in env_vars:
        return "https://x-access-token:{}@github.com/yourorg/TrackRat.git".format(
            env_vars["GH_TOKEN"]
        )

    # Local: use origin as-is
    return host.shell("git remote get-url origin").stdout.strip()

# Set up state storage
store.set(
    store.git(get_repo_url(), branch="ocuroot-state"),
    intent=store.git(get_repo_url(), branch="ocuroot-intent")
)

# Configure remotes
remotes([get_repo_url()])

# ... rest of file
```

**Also need:**
1. Create `ocuroot-state` and `ocuroot-intent` branches
2. Add `GH_TOKEN` to CI environment

---

### 3. Incorrect Task Registration Pattern

**File:** `backend_v2/release.ocu.star:308-316`

**Problem:**
```python
phase(
    "build",
    work=[
        task(
            build,
            name="build-backend"
        )
    ]
)
```

**Issue:** Using nested `task()` call inside `work=[]`. According to docs, should be:

```python
# For tasks outside phases
task(build, name="build-backend")

# OR for tasks inside phases
phase(
    "build",
    work=[build]  # Just the function reference
)
```

**Impact:** May cause ocuroot parser errors or unexpected behavior.

**Fix:**

```python
# Phase 1: Build
task(build, name="build-backend", inputs={
    "prev_build_number": input(
        ref="./call/build-backend#output/build_number",
        default=0
    ),
})

# Phase 2: Deploy to Staging
phase(
    "staging",
    work=[
        deploy(
            up=deploy_infrastructure,
            down=rollback_infrastructure,
            environment=e,
            inputs={
                "image_tag": input(ref="./call/build-backend#output/image_tag")
            }
        ) for e in environments() if e.attributes.get("type") == "staging"
    ]
)
```

**Note:** Tasks outside phases should use `task()`, tasks inside phases go directly in `work=[]` list.

---

### 4. Missing Input Declarations

**File:** `backend_v2/release.ocu.star:15`

**Problem:**
```python
def build(prev_build_number=None, year=None, month=None, day=None, sha=None, gcp_project=None, environment=None):
```

**Issue:** Function has parameters but no corresponding `inputs={}` declaration in task registration.

**Impact:** Ocuroot won't know where to get these values. Parameters will always be None.

**Fix:**

```python
task(
    build,
    name="build-backend",
    inputs={
        "prev_build_number": input(
            ref="./call/build-backend#output/build_number",
            default=0
        ),
        "sha": input(ref="@/custom/git_sha"),
        "gcp_project": input(ref="@/environment/staging#attributes/gcp_project"),
        "environment": input(ref="@/environment/staging#attributes/type"),
    }
)
```

**Or simpler:** Remove unused parameters and rely on function defaults.

---

## Major Issues (Should Fix)

### 5. Docker Build Outside Ocuroot

**File:** `backend_v2/release.ocu.star:86-98`, `.github/workflows/ci-cd.yml:160-200`

**Problem:** Docker image is built in CI test job (lines 160-200), but `build()` function also contains Docker build commands (lines 86-98).

**Issue:** Duplication and unclear responsibility. Which build is canonical?

**Current flow:**
1. CI builds and pushes image (lines 160-200)
2. Ocuroot `build()` runs and builds image again? (lines 86-98)
3. Unclear if Ocuroot build actually runs

**Impact:**
- Potential double builds (wasteful)
- Version mismatch if builds differ
- Confusion about source of truth

**Fix Option 1 - CI builds, Ocuroot deploys:**
```python
# Change build() to just tag/version, not build
def build(prev_build_number=None, sha=None, gcp_project=None):
    """Generate version tag for pre-built Docker image"""
    build_number = (prev_build_number or 0) + 1

    if not sha:
        sha = host.shell("git rev-parse HEAD").stdout.strip()

    # Generate version (matches CI)
    year = host.shell("date +%Y").stdout.strip()
    month = host.shell("date +%m").stdout.strip()
    day = host.shell("date +%d").stdout.strip()

    version = "{}.{}.{}-build{}-{}".format(year, month, day, build_number, sha[:7])

    # Image already built by CI
    project_id = gcp_project or "trackrat-staging"
    env = "staging" if "staging" in project_id else "production"
    repository = "trackcast-inference-staging" if env == "staging" else "trackcast-inference-prod"

    image_tag = "us-central1-docker.pkg.dev/{}/{}/trackcast-inference:{}".format(
        project_id, repository, version
    )

    return {
        "build_number": build_number,
        "image_tag": image_tag,
        "version": version,
    }
```

**Fix Option 2 - Ocuroot builds:**
```yaml
# Remove Docker build from CI, let Ocuroot handle it
# Delete lines 160-200 from ci-cd.yml
# Keep build() function as-is
```

**Recommendation:** Option 1 (CI builds) is better because:
- Faster feedback (build during tests)
- Can use GitHub Actions caching
- Build once, deploy many times

---

### 6. Inconsistent Service Name

**File:** `backend_v2/release.ocu.star:183`, `environments/release.ocu.star:28,70`

**Problem:**
```python
# In release.ocu.star:183
environment.attributes["service_name"]  # Expects "service_name" attribute

# In environments/release.ocu.star:28,70
"service_name": "trackrat-api-staging"  # Defined correctly

# But in gcloud command (line 178-186):
gcloud run services describe {} ...  # Uses service_name from attributes
```

**Issue:** Code expects `service_name` attribute but it's defined. Actually this is correct!

**Wait, re-checking...**

Actually, this is **fine**. Both environments define `service_name` correctly.

---

### 7. Missing Store/Load for Libraries

**File:** `lib/terraform.star:1`, `lib/secrets.star:1`

**Problem:** Library files don't have `ocuroot()` version declaration.

**Issue:** May not be valid Starlark modules for Ocuroot.

**Impact:** Unclear. May work anyway since they're loaded, not executed as releases.

**Fix (if needed):**

```python
# lib/terraform.star
# No ocuroot() declaration needed for library files

# Confirmed from docs: Only release.ocu.star files need ocuroot("0.3.0")
```

**Actually:** Libraries don't need `ocuroot()` declaration. This is **correct**.

---

## Minor Issues (Nice to Have)

### 8. Hardcoded Terraform Directory

**File:** `lib/terraform.star:27`

**Problem:**
```python
tf_dir = "infra/environments/{}".format(environment.attributes["terraform_env"])
```

**Issue:** Hardcoded path structure. If infra layout changes, breaks.

**Fix:**

```python
# Add to environment attributes
"terraform_dir": "infra/environments/staging"

# Use in terraform.star
tf_dir = environment.attributes.get("terraform_dir",
    "infra/environments/{}".format(environment.attributes["terraform_env"])
)
```

---

### 9. No Error Handling in shell() Calls

**File:** `lib/secrets.star:48-66`

**Problem:**
```python
create_result = host.shell(
    "echo -n '{}' | gcloud secrets create ...",
    check=False,
    capture_output=True
)

if create_result.returncode == 0:
    return

# If creation failed, add version
update_result = host.shell("echo -n '{}' | gcloud secrets versions add ...", check=False)

if update_result.returncode != 0:
    fail("Failed to create or update secret")
```

**Issue:** Using shell commands with string interpolation (`'{}'`) is vulnerable to injection if `value` contains quotes.

**Fix:**

```python
# Use proper escaping or file-based input
def set_secret(secret_name, value, project_id):
    # Write value to temp file
    temp_file = "/tmp/ocuroot-secret-{}".format(secret_name)
    host.shell("echo -n '{}' > {}".format(value.replace("'", "'\\''"), temp_file))

    # Create secret from file
    create_result = host.shell(
        "gcloud secrets create {} --data-file={} --project={} --replication-policy=automatic".format(
            secret_name, temp_file, project_id
        ),
        check=False
    )

    # Clean up
    host.shell("rm -f {}".format(temp_file))
```

**Or better:** Use `stdin` if Starlark supports it.

---

### 10. Missing Rollback Test

**File:** `backend_v2/release.ocu.star:256-301`

**Problem:** `rollback_infrastructure()` function exists but production phase is commented out.

**Issue:** Rollback never tested in production.

**Fix:** Uncomment production phase and test rollback before going live.

---

### 11. Verbose Logging Could Be Structured

**File:** Multiple files use `print()` for logging

**Issue:** No log levels (INFO, WARN, ERROR). Everything printed at same level.

**Impact:** Hard to filter important vs debug messages.

**Fix:** Not critical, but could add severity prefixes:

```python
print("ℹ️  INFO: Initializing Terraform...")
print("⚠️  WARN: Service URL not in outputs...")
print("❌ ERROR: Health checks failed")
```

---

## Correctness Review

### ✅ What's Correct

1. **File structure**: All `.ocu.star` files in correct locations
2. **Function signatures**: Build, deploy, rollback functions follow patterns
3. **Terraform integration**: Proper use of lib/terraform.star abstraction
4. **Environment definitions**: Staging and production well-configured
5. **Health checks**: Comprehensive verification in `verify_deployment()`
6. **Secret storage**: Good use of GCP Secret Manager for outputs
7. **Ocuroot version**: Using v0.3.16 consistently
8. **Installation**: Tar.gz extraction fixed correctly

### ❌ What's Incorrect

1. **Version inputs**: Reference non-existent step outputs (CRITICAL)
2. **State configuration**: Missing `store.set()` and `remotes()` (CRITICAL)
3. **Task registration**: Wrong pattern with `work=[task(...)]` (MAJOR)
4. **Input declarations**: Build function inputs not declared (MAJOR)
5. **Docker build location**: Unclear if CI or Ocuroot builds (MAJOR)

### ⚠️ What's Questionable

1. **No remote state**: Using local state by default
2. **Hardcoded paths**: Terraform directory structure assumed
3. **String interpolation**: Potential injection in secrets
4. **No integration tests**: Rollback untested
5. **Version mismatch**: CI version vs Ocuroot version could differ

---

## Recommended Action Plan

### Phase 1: Critical Fixes (Before First Deploy)

1. **Fix version inputs** (`.github/workflows/ci-cd.yml`)
   - Remove `OCUROOT_INPUT_year/month/day`
   - Let `build()` determine date components
   - Or add version parsing step

2. **Add state configuration** (`backend_v2/release.ocu.star`, `environments/release.ocu.star`)
   - Add `store.set()` with Git backend
   - Add `remotes()` configuration
   - Create `ocuroot-state` and `ocuroot-intent` branches
   - Configure `GH_TOKEN` in CI

3. **Fix task registration** (`backend_v2/release.ocu.star`)
   - Move `task(build)` outside phase
   - Remove `work=[task(...)]` pattern
   - Add proper `inputs={}` declarations

### Phase 2: Major Improvements (Before Production)

1. **Clarify build responsibility**
   - Decision: CI builds, Ocuroot tags
   - Update `build()` to be version-only
   - Or: Remove CI build, let Ocuroot handle

2. **Test rollback**
   - Uncomment production phase
   - Run rollback in staging
   - Verify Secret Manager integration

3. **Add error handling**
   - Fix string interpolation in secrets.star
   - Add retry logic for transient failures

### Phase 3: Nice to Have (Post-Launch)

1. **Structured logging**
   - Add log level prefixes
   - Consider JSON logging

2. **Configuration externalization**
   - Move hardcoded paths to environment attributes
   - Make Terraform directory configurable

3. **Documentation**
   - Add comments to `.ocu.star` files
   - Document state branches in README
   - Create runbook for rollbacks

---

## Testing Checklist

Before declaring production-ready:

- [ ] Fix version inputs or remove them
- [ ] Add state configuration and create branches
- [ ] Fix task registration pattern
- [ ] Test staging deployment end-to-end
- [ ] Verify health checks work
- [ ] Test rollback in staging
- [ ] Verify state is stored in Git
- [ ] Check Ocuroot state via web UI
- [ ] Test manual release trigger
- [ ] Verify outputs stored in Secret Manager
- [ ] Test service URL extraction
- [ ] Uncomment production phase
- [ ] Review Terraform state isolation

---

## Comparison to Ocuroot Best Practices

| Practice | Status | Notes |
|----------|--------|-------|
| Version declaration | ✅ | `ocuroot("0.3.0")` present |
| Git-based state | ❌ | Missing `store.set()` |
| Remote configuration | ❌ | Missing `remotes()` |
| Input declarations | ❌ | Missing `inputs={}` in task() |
| Phase grouping | ✅ | Proper staging/production phases |
| Deploy up/down | ✅ | Both functions implemented |
| Self-referencing | ⚠️ | Attempted but inputs missing |
| Environment attributes | ✅ | Well-structured attributes |
| Health checks | ✅ | Comprehensive verification |
| Rollback capability | ✅ | Implemented (untested) |
| Dependency cascade | ⚠️ | Uses `--cascade` but deps unclear |
| State persistence | ✅ | Secret Manager for outputs |

**Overall Grade:** C+ (66%)
- **Functionality:** B (works in local mode)
- **Best Practices:** D (missing state, remotes, inputs)
- **Production Readiness:** C (needs fixes before prod)

---

## Conclusion

The Ocuroot implementation is **structurally sound** but has several **critical configuration issues** that prevent it from being production-ready. The main problems are:

1. Missing state/remote configuration (breaks team collaboration)
2. Incorrect CI version input references (breaks deployment)
3. Missing input declarations (breaks dependency tracking)
4. Unclear Docker build responsibility (potential duplication)

**Recommendation:** Fix critical issues before first staging deployment. Current implementation would work in `OCUROOT_LOCAL_MODE=true` for testing but not ready for Git-based team workflow.

**Estimated Fix Time:** 2-4 hours for critical fixes, 1 day for comprehensive testing.
