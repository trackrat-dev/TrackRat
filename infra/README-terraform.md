<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.0 |
| <a name="requirement_google"></a> [google](#requirement\_google) | ~> 5.0 |
| <a name="requirement_google-beta"></a> [google-beta](#requirement\_google-beta) | ~> 5.0 |
| <a name="requirement_random"></a> [random](#requirement\_random) | ~> 3.4 |

## Providers

No providers.

## Modules

| Name | Source | Version |
|------|--------|---------|
| <a name="module_apis"></a> [apis](#module\_apis) | ./modules/apis | n/a |
| <a name="module_artifact_registry"></a> [artifact\_registry](#module\_artifact\_registry) | ./modules/artifact-registry | n/a |
| <a name="module_secrets"></a> [secrets](#module\_secrets) | ./modules/secrets | n/a |
| <a name="module_vpc"></a> [vpc](#module\_vpc) | ./modules/vpc | n/a |

## Resources

No resources.

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_app_name"></a> [app\_name](#input\_app\_name) | Application name | `string` | `"trackrat"` | no |
| <a name="input_artifact_registry_repository_name"></a> [artifact\_registry\_repository\_name](#input\_artifact\_registry\_repository\_name) | Custom Artifact Registry repository name (optional). If not provided, defaults to {app\_name}-{environment} | `string` | `""` | no |
| <a name="input_environment"></a> [environment](#input\_environment) | Environment name (dev, staging, prod) | `string` | n/a | yes |
| <a name="input_project_id"></a> [project\_id](#input\_project\_id) | The GCP project ID | `string` | n/a | yes |
| <a name="input_region"></a> [region](#input\_region) | The GCP region | `string` | `"us-east1"` | no |
| <a name="input_subnet_cidr"></a> [subnet\_cidr](#input\_subnet\_cidr) | CIDR block for subnet | `string` | `"10.0.1.0/24"` | no |
| <a name="input_vpc_cidr"></a> [vpc\_cidr](#input\_vpc\_cidr) | CIDR block for VPC | `string` | `"10.0.0.0/16"` | no |
| <a name="input_zone"></a> [zone](#input\_zone) | The GCP zone | `string` | `"us-east1-b"` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_artifact_registry_repository"></a> [artifact\_registry\_repository](#output\_artifact\_registry\_repository) | Artifact Registry repository for Docker images |
| <a name="output_network_self_link"></a> [network\_self\_link](#output\_network\_self\_link) | The self-link of the VPC network. |
| <a name="output_project_id"></a> [project\_id](#output\_project\_id) | GCP project ID |
| <a name="output_region"></a> [region](#output\_region) | GCP region |
| <a name="output_secret_manager_secret_name"></a> [secret\_manager\_secret\_name](#output\_secret\_manager\_secret\_name) | Name of the Secret Manager secret |
| <a name="output_vpc_network_name"></a> [vpc\_network\_name](#output\_vpc\_network\_name) | Name of the VPC network |
| <a name="output_vpc_subnet_name"></a> [vpc\_subnet\_name](#output\_vpc\_subnet\_name) | Name of the VPC subnet |
<!-- END_TF_DOCS -->