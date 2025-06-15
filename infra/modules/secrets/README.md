<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.0 |
| <a name="requirement_google"></a> [google](#requirement\_google) | >= 5.0 |
| <a name="requirement_random"></a> [random](#requirement\_random) | ~> 3.4 |

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
| [google_secret_manager_secret_version.app_secrets_version](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/secret_manager_secret_version) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_amtrak_api_key"></a> [amtrak\_api\_key](#input\_amtrak\_api\_key) | Amtrak API key (optional) | `string` | `""` | no |
| <a name="input_app_name"></a> [app\_name](#input\_app\_name) | Application name | `string` | n/a | yes |
| <a name="input_database_host"></a> [database\_host](#input\_database\_host) | Database host/IP address | `string` | `""` | no |
| <a name="input_database_name"></a> [database\_name](#input\_database\_name) | Database name | `string` | `""` | no |
| <a name="input_database_password"></a> [database\_password](#input\_database\_password) | Database password | `string` | `""` | no |
| <a name="input_database_user"></a> [database\_user](#input\_database\_user) | Database user name | `string` | `""` | no |
| <a name="input_environment"></a> [environment](#input\_environment) | Environment name (dev, staging, prod) | `string` | n/a | yes |
| <a name="input_nj_transit_password"></a> [nj\_transit\_password](#input\_nj\_transit\_password) | NJ Transit API password | `string` | `""` | no |
| <a name="input_nj_transit_username"></a> [nj\_transit\_username](#input\_nj\_transit\_username) | NJ Transit API username | `string` | `""` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_secret_id"></a> [secret\_id](#output\_secret\_id) | ID of the Secret Manager secret |
| <a name="output_secret_name"></a> [secret\_name](#output\_secret\_name) | Name of the Secret Manager secret |
<!-- END_TF_DOCS -->