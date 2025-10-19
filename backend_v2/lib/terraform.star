"""Terraform wrapper for Ocuroot integration

This module provides a clean interface for running Terraform operations
within Ocuroot release workflows, handling initialization, planning, and
applying changes with proper state management.
"""

def setup_terraform(environment, module_name):
    """Setup Terraform with GCS backend for the given environment and module

    Args:
        environment: Ocuroot environment object with attributes
        module_name: Name of the module being deployed (for cache isolation)

    Returns:
        Struct with init, plan, apply, destroy functions
    """

    # Extract environment configuration
    project_id = environment["attributes"]["gcp_project"]
    tf_state_bucket = "{}-terraform-state".format(project_id)
    tf_state_prefix = "terraform/state"

    # Setup working directory
    tf_dir = "infra/environments/{}".format(environment["attributes"]["terraform_env"])
    cache_dir = ".ocuroot/terraform/{}/{}".format(environment["name"], module_name)

    # Backend configuration for GCS
    backend_config = [
        "bucket={}".format(tf_state_bucket),
        "prefix={}".format(tf_state_prefix)
    ]

    def _ensure_terraform():
        """Ensure Terraform is installed"""
        # Check if terraform is available
        check_result = host.shell(
            "which terraform",
            capture_output=True,
            check=False
        )

        if check_result.returncode != 0:
            print("⚠️  Terraform not found, attempting installation...")

            # Detect OS and install accordingly
            os_type = host.shell("uname -s", capture_output=True).stdout.strip().lower()

            if os_type == "darwin":
                # macOS with Homebrew
                print("Installing Terraform via Homebrew...")
                host.shell("brew tap hashicorp/tap")
                host.shell("brew install hashicorp/tap/terraform")
            elif os_type == "linux":
                # Linux with apt
                print("Installing Terraform via apt...")
                host.shell("wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg")
                host.shell('echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list')
                host.shell("sudo apt update && sudo apt install terraform -y")
            else:
                fail("Unsupported OS: {}. Please install Terraform manually.".format(os_type))

            print("✅ Terraform installed successfully")

    def _build_env_vars(vars={}):
        """Build environment variables for Terraform, including TF_VAR_ prefixed variables"""
        env_vars = {"TF_DATA_DIR": cache_dir}

        # Add all custom variables with TF_VAR_ prefix
        for k, v in vars.items():
            env_vars["TF_VAR_{}".format(k)] = str(v)

        return env_vars

    def init():
        """Initialize Terraform with GCS backend"""
        _ensure_terraform()

        print("🔧 Initializing Terraform for {} environment...".format(environment["name"]))
        print("   Working directory: {}".format(tf_dir))
        print("   State bucket: {}".format(tf_state_bucket))
        print("   Cache directory: {}".format(cache_dir))

        # Build backend config arguments
        backend_args = " ".join(["-backend-config={}".format(c) for c in backend_config])

        # Initialize
        result = host.shell(
            "terraform init {}".format(backend_args),
            dir=tf_dir,
            env={"TF_DATA_DIR": cache_dir}
        )

        if result.returncode != 0:
            fail("Terraform init failed")

        print("✅ Terraform initialized")

    def validate():
        """Validate Terraform configuration"""
        print("🔍 Validating Terraform configuration...")

        result = host.shell(
            "terraform validate",
            dir=tf_dir,
            env={"TF_DATA_DIR": cache_dir}
        )

        if result.returncode != 0:
            fail("Terraform validation failed")

        print("✅ Terraform configuration is valid")

    def plan(vars={}):
        """Run terraform plan

        Args:
            vars: Dictionary of Terraform variables

        Returns:
            Plan result
        """
        print("📋 Planning Terraform changes...")
        print("   Variables: {}".format(vars))

        env_vars = _build_env_vars(vars)

        result = host.shell(
            "terraform plan -out=tfplan",
            dir=tf_dir,
            env=env_vars
        )

        if result.returncode != 0:
            fail("Terraform plan failed")

        print("✅ Terraform plan completed")
        return result

    def apply(vars={}):
        """Apply Terraform configuration

        Args:
            vars: Dictionary of Terraform variables

        Returns:
            Dictionary of Terraform outputs
        """
        print("🚀 Applying Terraform changes...")

        env_vars = _build_env_vars(vars)

        # Apply the plan
        result = host.shell(
            "terraform apply -auto-approve tfplan",
            dir=tf_dir,
            env=env_vars
        )

        if result.returncode != 0:
            fail("Terraform apply failed")

        print("✅ Terraform apply completed")

        # Get outputs using individual terraform output commands
        print("📤 Retrieving Terraform outputs...")

        # Get service URL output
        outputs = {}
        service_url_result = host.shell(
            "terraform output -raw trackrat_api_service_url 2>/dev/null || echo ''",
            dir=tf_dir,
            env={"TF_DATA_DIR": cache_dir},
            capture_output=True,
            check=False
        )

        if service_url_result.returncode == 0 and service_url_result.stdout.strip():
            outputs["trackrat_api_service_url"] = service_url_result.stdout.strip()
            print("   Found service URL output")

        return outputs

    def destroy(vars={}):
        """Destroy Terraform resources

        Args:
            vars: Dictionary of Terraform variables
        """
        print("🗑️  Destroying Terraform resources...")
        print("⚠️  This will destroy infrastructure in {} environment!".format(environment["name"]))

        env_vars = _build_env_vars(vars)

        result = host.shell(
            "terraform destroy -auto-approve",
            dir=tf_dir,
            env=env_vars
        )

        if result.returncode != 0:
            fail("Terraform destroy failed")

        print("✅ Terraform destroy completed")

    def output():
        """Get Terraform outputs without applying

        Returns:
            Dictionary of Terraform outputs
        """
        print("📤 Retrieving Terraform outputs...")

        # Get service URL output
        outputs = {}
        service_url_result = host.shell(
            "terraform output -raw trackrat_api_service_url 2>/dev/null || echo ''",
            dir=tf_dir,
            env={"TF_DATA_DIR": cache_dir},
            capture_output=True,
            check=False
        )

        if service_url_result.returncode == 0 and service_url_result.stdout.strip():
            outputs["trackrat_api_service_url"] = service_url_result.stdout.strip()

        return outputs

    # Initialize on setup
    init()
    validate()

    return struct(
        init=init,
        validate=validate,
        plan=plan,
        apply=apply,
        destroy=destroy,
        output=output
    )
