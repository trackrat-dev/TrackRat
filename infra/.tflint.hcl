# TFLint configuration for TrackRat infrastructure
# https://github.com/terraform-linters/tflint/blob/master/docs/user-guide/config.md

config {
  # Enable all rules by default
  disabled_by_default = false
  
  # Set the format for output
  format = "compact"
  
  # Force color output (useful for CI)
  force = false
}

# Enable the Google provider plugin
plugin "google" {
  enabled = true
  version = "0.27.1"
  source  = "github.com/terraform-linters/tflint-ruleset-google"
}

# Core Terraform rules
rule "terraform_deprecated_interpolation" {
  enabled = true
}

rule "terraform_deprecated_index" {
  enabled = true
}

rule "terraform_unused_declarations" {
  enabled = true
}

rule "terraform_comment_syntax" {
  enabled = true
}

rule "terraform_documented_outputs" {
  enabled = true
}

rule "terraform_documented_variables" {
  enabled = true
}

rule "terraform_typed_variables" {
  enabled = true
}

rule "terraform_module_pinned_source" {
  enabled = true
}

rule "terraform_naming_convention" {
  enabled = true
  format  = "snake_case"
}

rule "terraform_standard_module_structure" {
  enabled = true
}


# Disable rules that might be too strict for our use case
rule "terraform_unused_required_providers" {
  enabled = false  # We might not use all providers in all modules
}
