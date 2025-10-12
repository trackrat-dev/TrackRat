"""GCP Secret Manager integration for Ocuroot

This module provides functions for reading and writing secrets to
GCP Secret Manager, used for passing deployment outputs and configuration
between Ocuroot phases and services.
"""

def get_secret(secret_name, project_id):
    """Get secret value from GCP Secret Manager

    Args:
        secret_name: Name of the secret to retrieve
        project_id: GCP project ID containing the secret

    Returns:
        Secret value as string
    """
    print("🔐 Reading secret: {} from project {}".format(secret_name, project_id))

    result = host.shell(
        "gcloud secrets versions access latest --secret={} --project={}".format(
            secret_name, project_id
        ),
        capture_output=True,
        check=False
    )

    if result.returncode != 0:
        print("⚠️  Secret '{}' not found or inaccessible".format(secret_name))
        return None

    value = result.stdout.strip()
    print("✅ Secret retrieved")
    return value

def set_secret(secret_name, value, project_id):
    """Create or update secret in GCP Secret Manager

    Args:
        secret_name: Name of the secret to create/update
        value: Secret value to store
        project_id: GCP project ID to store the secret in
    """
    print("🔐 Storing secret: {} in project {}".format(secret_name, project_id))

    # Try to create the secret first
    create_result = host.shell(
        "echo -n '{}' | gcloud secrets create {} --data-file=- --project={} --replication-policy=automatic".format(
            value, secret_name, project_id
        ),
        check=False,
        capture_output=True
    )

    if create_result.returncode == 0:
        print("✅ Secret created")
        return

    # If creation failed (likely already exists), add a new version
    print("   Secret exists, adding new version...")
    update_result = host.shell(
        "echo -n '{}' | gcloud secrets versions add {} --data-file=- --project={}".format(
            value, secret_name, project_id
        ),
        check=False
    )

    if update_result.returncode != 0:
        fail("Failed to create or update secret '{}'".format(secret_name))

    print("✅ Secret updated")

def store_output(key, value, environment):
    """Store a deployment output as a secret for cross-phase access

    This is useful for passing data between deployment phases or to other services.

    Args:
        key: Output key name
        value: Output value
        environment: Ocuroot environment object
    """
    secret_name = "ocuroot-output-{}-{}".format(environment.name, key)
    project_id = environment.attributes["gcp_project"]

    set_secret(secret_name, str(value), project_id)

def get_output(key, environment):
    """Retrieve a deployment output that was stored as a secret

    Args:
        key: Output key name
        environment: Ocuroot environment object

    Returns:
        Output value or None if not found
    """
    secret_name = "ocuroot-output-{}-{}".format(environment.name, key)
    project_id = environment.attributes["gcp_project"]

    return get_secret(secret_name, project_id)

def list_secrets(project_id, prefix=""):
    """List all secrets in a project, optionally filtered by prefix

    Args:
        project_id: GCP project ID
        prefix: Optional prefix to filter secrets

    Returns:
        List of secret names
    """
    print("📋 Listing secrets in project {}".format(project_id))
    if prefix:
        print("   Filtering by prefix: {}".format(prefix))

    result = host.shell(
        "gcloud secrets list --project={} --format='value(name)'".format(project_id),
        capture_output=True
    )

    if result.returncode != 0:
        print("⚠️  Failed to list secrets")
        return []

    secrets = [s.strip() for s in result.stdout.split("\n") if s.strip()]

    if prefix:
        secrets = [s for s in secrets if s.startswith(prefix)]

    print("   Found {} secrets".format(len(secrets)))
    return secrets
