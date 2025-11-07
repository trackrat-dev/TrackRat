"""TrackRat Repository Configuration

This file defines how Ocuroot manages the TrackRat repository,
including state storage and deployment triggers.
"""

ocuroot("0.3.0")

# Repository alias for referencing in release files
repo_alias("github.com/bokonon1/TrackRat")

# Configure state storage based on mode
# Local mode uses filesystem, cloud mode uses git
def setup_and_configure_store():
    env_vars = host.env()

    # Check if local mode is explicitly enabled (must be "true", "1", or "yes")
    local_mode_value = env_vars.get("OCUROOT_LOCAL_MODE", "")
    use_local_mode = local_mode_value.lower() in ["true", "1", "yes"]

    # Detect if we're running in CI based on GH_TOKEN presence
    in_ci = "GH_TOKEN" in env_vars

    if use_local_mode:
        print("🏠 OCUROOT LOCAL MODE")
        print("   State storage: ./.ocuroot/state")
        print("   Intent storage: ./.ocuroot/intent")
        print("")
        print("   To use git storage, unset OCUROOT_LOCAL_MODE or set to false")
        print("")

        state_store = store.fs("./.ocuroot/state")
        intent_store = store.fs("./.ocuroot/intent")
        store.set(state_store, intent=intent_store)
    else:
        # Cloud mode - use git backend for shared state
        env = env_vars.get("OCUROOT_ENV", "staging")

        print("☁️  OCUROOT CLOUD MODE")
        print("   Environment: {}".format(env))
        print("   State storage: Git repository")
        print("")

        # Use git backend pointing to the trackrat-ocuroot-state repository
        # In CI: use HTTPS with token authentication
        # Locally: use SSH authentication
        if in_ci:
            # CI mode - use HTTPS with token
            token = env_vars["GH_TOKEN"]
            state_url = "https://x-access-token:{}@github.com/bokonon1/trackrat-ocuroot-state.git".format(token)
            print("   Authentication: HTTPS with token (CI mode)")
        else:
            # Local development - use SSH
            state_url = "git@github.com:bokonon1/trackrat-ocuroot-state.git"
            print("   Authentication: SSH (local mode)")

        print("")

        store.set(
            store.git(state_url, branch="state"),
            intent=store.git(state_url, branch="intent"),
        )

# Initialize and configure store
setup_and_configure_store()

# Trigger handler for automatic workflow cascading
def do_trigger(commit):
    """Trigger GitHub Actions workflow for continued work"""

    print("🔔 Triggering work cascade for commit: {}".format(commit))

    env_vars = host.env()

    if "GH_TOKEN" not in env_vars:
        print("⚠️  GH_TOKEN not available, cannot trigger GitHub workflow")
        print("   Work will need to be triggered manually")
        return

    gh_token = env_vars["GH_TOKEN"]
    owner = "bokonon1"
    repo = "TrackRat"

    # Determine workflow based on environment
    env = env_vars.get("OCUROOT_ENV", "staging")
    workflow_id = "ocuroot-production.yml" if env == "production" else "ocuroot-staging.yml"
    ref = "production" if env == "production" else "main"

    # GitHub API endpoint
    url = "https://api.github.com/repos/{}/{}/actions/workflows/{}/dispatches".format(
        owner, repo, workflow_id
    )

    # Payload - construct JSON manually
    payload = '{"ref": "' + ref + '", "inputs": {"commit_sha": "' + commit + '", "triggered_by": "ocuroot-cascade"}}'

    # Headers
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": "token {}".format(gh_token),
        "X-GitHub-Api-Version": "2022-11-28"
    }

    print("   Workflow: {}".format(workflow_id))
    print("   Branch: {}".format(ref))

    # Trigger the workflow
    response = http.post(url=url, body=payload, headers=headers)

    if response["status_code"] == 204:
        print("✅ Successfully triggered workflow")
    else:
        print("❌ Failed to trigger workflow")
        print("   Status code: {}".format(response["status_code"]))
        if "body" in response:
            print("   Response: {}".format(response["body"]))

# Register trigger handler
trigger(do_trigger)
