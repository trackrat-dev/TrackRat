<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.0 |
| <a name="requirement_google"></a> [google](#requirement\_google) | >= 5.0 |
| <a name="requirement_random"></a> [random](#requirement\_random) | ~> 3.1 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_google"></a> [google](#provider\_google) | 5.45.2 |
| <a name="provider_random"></a> [random](#provider\_random) | ~> 3.1 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [google_monitoring_alert_policy.db_connectivity_lost](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/monitoring_alert_policy) | resource |
| [google_monitoring_alert_policy.db_high_cpu](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/monitoring_alert_policy) | resource |
| [google_monitoring_alert_policy.db_low_memory](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/monitoring_alert_policy) | resource |
| [google_monitoring_notification_channel.email_critical](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/monitoring_notification_channel) | resource |
| [google_monitoring_notification_channel.email_warning](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/monitoring_notification_channel) | resource |
| [google_secret_manager_secret.database_password](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/secret_manager_secret) | resource |
| [google_secret_manager_secret.database_url](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/secret_manager_secret) | resource |
| [google_secret_manager_secret_version.database_password_version](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/secret_manager_secret_version) | resource |
| [google_secret_manager_secret_version.database_url_version](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/secret_manager_secret_version) | resource |
| [google_sql_database.default](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/sql_database) | resource |
| [google_sql_database_instance.default](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/sql_database_instance) | resource |
| [google_sql_user.default](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/sql_user) | resource |
| [random_password.database_user_password](https://registry.terraform.io/providers/hashicorp/random/latest/docs/resources/password) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_backup_window_start_time"></a> [backup\_window\_start\_time](#input\_backup\_window\_start\_time) | The start time of the daily backup window, in HH:MM format (UTC). Example: '03:00'. If null, GCP chooses a default. | `string` | `"03:00"` | no |
| <a name="input_cpu_alert_threshold_percent"></a> [cpu\_alert\_threshold\_percent](#input\_cpu\_alert\_threshold\_percent) | CPU utilization percentage threshold for alerting. | `number` | `80` | no |
| <a name="input_critical_alert_email"></a> [critical\_alert\_email](#input\_critical\_alert\_email) | Email address for critical alerts. | `string` | n/a | yes |
| <a name="input_database_name"></a> [database\_name](#input\_database\_name) | The name of the database to create. | `string` | `"trackratdb"` | no |
| <a name="input_database_user_name"></a> [database\_user\_name](#input\_database\_user\_name) | The name of the database user. | `string` | `"trackratuser"` | no |
| <a name="input_database_version"></a> [database\_version](#input\_database\_version) | The version of PostgreSQL to use (e.g., POSTGRES\_15). | `string` | `"POSTGRES_15"` | no |
| <a name="input_deletion_protection"></a> [deletion\_protection](#input\_deletion\_protection) | Whether or not to enable deletion protection for the instance. | `bool` | `false` | no |
| <a name="input_instance_name"></a> [instance\_name](#input\_instance\_name) | The name of the Cloud SQL instance. | `string` | `"trackrat-db-instance"` | no |
| <a name="input_instance_tier"></a> [instance\_tier](#input\_instance\_tier) | The machine type for the Cloud SQL instance (e.g., db-custom-2-7680). | `string` | `"db-g1-small"` | no |
| <a name="input_log_connections"></a> [log\_connections](#input\_log\_connections) | Log connections to the database (flag: log\_connections). | `bool` | `false` | no |
| <a name="input_log_disconnections"></a> [log\_disconnections](#input\_log\_disconnections) | Log disconnections from the database (flag: log\_disconnections). | `bool` | `false` | no |
| <a name="input_maintenance_window_day"></a> [maintenance\_window\_day](#input\_maintenance\_window\_day) | The day of the week for the maintenance window (1-7, Monday-Sunday). | `number` | `7` | no |
| <a name="input_maintenance_window_hour"></a> [maintenance\_window\_hour](#input\_maintenance\_window\_hour) | The hour of the day (UTC) for the maintenance window (0-23). | `number` | `6` | no |
| <a name="input_max_connections_limit"></a> [max\_connections\_limit](#input\_max\_connections\_limit) | The maximum number of concurrent connections for the database (flag: max\_connections). Default depends on instance size. | `number` | `100` | no |
| <a name="input_memory_alert_threshold_gb"></a> [memory\_alert\_threshold\_gb](#input\_memory\_alert\_threshold\_gb) | Available memory threshold in GB for alerting. | `number` | `1.4` | no |
| <a name="input_network_self_link"></a> [network\_self\_link](#input\_network\_self\_link) | The self-link of the VPC network to attach the Cloud SQL instance to. | `string` | n/a | yes |
| <a name="input_project_id"></a> [project\_id](#input\_project\_id) | The ID of the Google Cloud project. | `string` | n/a | yes |
| <a name="input_region"></a> [region](#input\_region) | The region for the Cloud SQL instance. | `string` | n/a | yes |
| <a name="input_service_networking_connection"></a> [service\_networking\_connection](#input\_service\_networking\_connection) | The service networking connection for private services (used for dependency) | `any` | `null` | no |
| <a name="input_slow_query_log_min_duration"></a> [slow\_query\_log\_min\_duration](#input\_slow\_query\_log\_min\_duration) | Minimum query duration in ms to be logged as a slow query. Use 0 to disable. For PostgreSQL, this is 'log\_min\_duration\_statement'. | `number` | `500` | no |
| <a name="input_warning_alert_email"></a> [warning\_alert\_email](#input\_warning\_alert\_email) | Email address for warning alerts. | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_database_name"></a> [database\_name](#output\_database\_name) | The name of the database created. |
| <a name="output_database_password"></a> [database\_password](#output\_database\_password) | The database user password (sensitive) |
| <a name="output_database_url_secret_name"></a> [database\_url\_secret\_name](#output\_database\_url\_secret\_name) | Name of the database URL secret |
| <a name="output_database_user_name"></a> [database\_user\_name](#output\_database\_user\_name) | The name of the default database user created. |
| <a name="output_db_password_secret_id"></a> [db\_password\_secret\_id](#output\_db\_password\_secret\_id) | The ID of the Secret Manager secret holding the DB password. |
| <a name="output_db_password_secret_version_id"></a> [db\_password\_secret\_version\_id](#output\_db\_password\_secret\_version\_id) | The ID of the Secret Manager secret version holding the DB password. |
| <a name="output_instance_connection_name"></a> [instance\_connection\_name](#output\_instance\_connection\_name) | The connection name of the Cloud SQL instance, used by Cloud SQL Proxy and connectors. |
| <a name="output_instance_name"></a> [instance\_name](#output\_instance\_name) | The name of the Cloud SQL instance. |
| <a name="output_instance_self_link"></a> [instance\_self\_link](#output\_instance\_self\_link) | The self-link of the Cloud SQL instance. |
| <a name="output_instance_service_account_email"></a> [instance\_service\_account\_email](#output\_instance\_service\_account\_email) | The email address of the service account associated with this Cloud SQL instance. |
| <a name="output_private_ip_address"></a> [private\_ip\_address](#output\_private\_ip\_address) | The private IP address of the Cloud SQL instance. |
<!-- END_TF_DOCS -->