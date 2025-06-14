<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.0 |
| <a name="requirement_google"></a> [google](#requirement\_google) | ~> 5.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_google"></a> [google](#provider\_google) | 5.45.2 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [google_secret_manager_secret.app_secrets](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/secret_manager_secret) | resource |
| [google_secret_manager_secret.db_password](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/secret_manager_secret) | resource |
| [google_secret_manager_secret_version.app_secrets_version](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/secret_manager_secret_version) | resource |
| [google_secret_manager_secret_version.db_password_version](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/secret_manager_secret_version) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_app_name"></a> [app\_name](#input\_app\_name) | Application name | `string` | n/a | yes |
| <a name="input_db_password_plaintext"></a> [db\_password\_plaintext](#input\_db\_password\_plaintext) | The plaintext database password to be stored in Secret Manager. This should be provided securely. | `string` | `null` | no |
| <a name="input_environment"></a> [environment](#input\_environment) | Environment name (dev, staging, prod) | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_db_password_secret_id"></a> [db\_password\_secret\_id](#output\_db\_password\_secret\_id) | The secret\_id of the database password secret in Secret Manager. |
| <a name="output_db_password_secret_name"></a> [db\_password\_secret\_name](#output\_db\_password\_secret\_name) | The full resource name of the database password secret. |
| <a name="output_db_password_secret_version_name"></a> [db\_password\_secret\_version\_name](#output\_db\_password\_secret\_version\_name) | The resource name of the latest version of the database password secret. |
| <a name="output_secret_id"></a> [secret\_id](#output\_secret\_id) | ID of the Secret Manager secret |
| <a name="output_secret_name"></a> [secret\_name](#output\_secret\_name) | Name of the Secret Manager secret |
<!-- END_TF_DOCS -->