<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.0 |
| <a name="requirement_google"></a> [google](#requirement\_google) | >= 4.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_google"></a> [google](#provider\_google) | 6.39.0 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [google_vpc_access_connector.default](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/vpc_access_connector) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_ip_cidr_range"></a> [ip\_cidr\_range](#input\_ip\_cidr\_range) | IP CIDR range for the VPC Access Connector (must be /28) | `string` | n/a | yes |
| <a name="input_name"></a> [name](#input\_name) | Name of the VPC Access Connector | `string` | n/a | yes |
| <a name="input_network_name"></a> [network\_name](#input\_network\_name) | Name of the VPC network | `string` | n/a | yes |
| <a name="input_region"></a> [region](#input\_region) | GCP region for the VPC Access Connector | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_id"></a> [id](#output\_id) | Self-link of the VPC Access Connector |
| <a name="output_name"></a> [name](#output\_name) | Name of the VPC Access Connector |
| <a name="output_state"></a> [state](#output\_state) | State of the VPC Access Connector |
<!-- END_TF_DOCS -->