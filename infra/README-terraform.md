<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.0 |
| <a name="requirement_google"></a> [google](#requirement\_google) | ~> 5.0 |
| <a name="requirement_google-beta"></a> [google-beta](#requirement\_google-beta) | ~> 5.0 |
| <a name="requirement_random"></a> [random](#requirement\_random) | ~> 3.4 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_google"></a> [google](#provider\_google) | 5.45.2 |

## Modules

| Name | Source | Version |
|------|--------|---------|
| <a name="module_apis"></a> [apis](#module\_apis) | ./modules/apis | n/a |
| <a name="module_artifact_registry"></a> [artifact\_registry](#module\_artifact\_registry) | ./modules/artifact-registry | n/a |
| <a name="module_secrets"></a> [secrets](#module\_secrets) | ./modules/secrets | n/a |
| <a name="module_vpc"></a> [vpc](#module\_vpc) | ./modules/vpc | n/a |

## Resources

| Name | Type |
|------|------|
| [google_storage_bucket.db_backup](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/storage_bucket) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_amtrak_api_key"></a> [amtrak\_api\_key](#input\_amtrak\_api\_key) | Amtrak API key (optional) | `string` | `""` | no |
| <a name="input_apns_auth_key"></a> [apns\_auth\_key](#input\_apns\_auth\_key) | APNS Auth Key (P8 content) | `string` | `""` | no |
| <a name="input_apns_key_id"></a> [apns\_key\_id](#input\_apns\_key\_id) | APNS Auth Key ID | `string` | `""` | no |
| <a name="input_apns_team_id"></a> [apns\_team\_id](#input\_apns\_team\_id) | Apple Developer Team ID for APNS | `string` | `""` | no |
| <a name="input_app_name"></a> [app\_name](#input\_app\_name) | Application name | `string` | `"trackrat"` | no |
| <a name="input_artifact_registry_repository_name"></a> [artifact\_registry\_repository\_name](#input\_artifact\_registry\_repository\_name) | Custom Artifact Registry repository name (optional). If not provided, defaults to {app\_name}-{environment} | `string` | `""` | no |
| <a name="input_environment"></a> [environment](#input\_environment) | Environment name (dev, staging, prod) | `string` | n/a | yes |
| <a name="input_nj_transit_password"></a> [nj\_transit\_password](#input\_nj\_transit\_password) | NJ Transit API password | `string` | `""` | no |
| <a name="input_nj_transit_token"></a> [nj\_transit\_token](#input\_nj\_transit\_token) | NJ Transit API token (alternative to username/password) | `string` | `""` | no |
| <a name="input_nj_transit_username"></a> [nj\_transit\_username](#input\_nj\_transit\_username) | NJ Transit API username | `string` | `""` | no |
| <a name="input_private_service_connection_ip_range"></a> [private\_service\_connection\_ip\_range](#input\_private\_service\_connection\_ip\_range) | The IP CIDR range to reserve for private service connection (e.g., Cloud SQL, Memorystore). Must be /20 or shorter prefix for sufficient capacity. | `string` | `"10.100.0.0/20"` | no |
| <a name="input_project_id"></a> [project\_id](#input\_project\_id) | The GCP project ID | `string` | n/a | yes |
| <a name="input_region"></a> [region](#input\_region) | The GCP region | `string` | `"us-east1"` | no |
| <a name="input_subnet_cidr"></a> [subnet\_cidr](#input\_subnet\_cidr) | CIDR block for subnet | `string` | `"10.0.1.0/24"` | no |
| <a name="input_vpc_cidr"></a> [vpc\_cidr](#input\_vpc\_cidr) | CIDR block for VPC | `string` | `"10.0.0.0/16"` | no |
| <a name="input_zone"></a> [zone](#input\_zone) | The GCP zone | `string` | `"us-east1-b"` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_amtrak_api_key_secret_name"></a> [amtrak\_api\_key\_secret\_name](#output\_amtrak\_api\_key\_secret\_name) | Name of the Amtrak API key secret |
| <a name="output_apns_auth_key_secret_name"></a> [apns\_auth\_key\_secret\_name](#output\_apns\_auth\_key\_secret\_name) | Name of the APNS Auth Key secret |
| <a name="output_apns_key_id_secret_name"></a> [apns\_key\_id\_secret\_name](#output\_apns\_key\_id\_secret\_name) | Name of the APNS Key ID secret |
| <a name="output_apns_team_id_secret_name"></a> [apns\_team\_id\_secret\_name](#output\_apns\_team\_id\_secret\_name) | Name of the APNS Team ID secret |
| <a name="output_artifact_registry_repository"></a> [artifact\_registry\_repository](#output\_artifact\_registry\_repository) | Artifact Registry repository for Docker images |
| <a name="output_db_backup_bucket_name"></a> [db\_backup\_bucket\_name](#output\_db\_backup\_bucket\_name) | Name of the GCS bucket for database backups |
| <a name="output_network_self_link"></a> [network\_self\_link](#output\_network\_self\_link) | The self-link of the VPC network. |
| <a name="output_njt_password_secret_name"></a> [njt\_password\_secret\_name](#output\_njt\_password\_secret\_name) | Name of the NJ Transit password secret |
| <a name="output_njt_token_secret_name"></a> [njt\_token\_secret\_name](#output\_njt\_token\_secret\_name) | Name of the NJ Transit token secret |
| <a name="output_njt_username_secret_name"></a> [njt\_username\_secret\_name](#output\_njt\_username\_secret\_name) | Name of the NJ Transit username secret |
| <a name="output_project_id"></a> [project\_id](#output\_project\_id) | GCP project ID |
| <a name="output_region"></a> [region](#output\_region) | GCP region |
| <a name="output_service_networking_connection"></a> [service\_networking\_connection](#output\_service\_networking\_connection) | The service networking connection for private services |
| <a name="output_vpc_network_name"></a> [vpc\_network\_name](#output\_vpc\_network\_name) | Name of the VPC network |
| <a name="output_vpc_subnet_name"></a> [vpc\_subnet\_name](#output\_vpc\_subnet\_name) | Name of the VPC subnet |
<!-- END_TF_DOCS -->