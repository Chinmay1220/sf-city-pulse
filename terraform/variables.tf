variable "snowflake_organization_name" {
  description = "Snowflake organization name."
  type        = string
}

variable "snowflake_account_name" {
  description = "Snowflake account name."
  type        = string
}

variable "snowflake_user" {
  description = "Admin user Terraform uses to provision Snowflake resources."
  type        = string
}

variable "snowflake_password" {
  description = "Admin user password."
  type        = string
  sensitive   = true
}

variable "snowflake_admin_role" {
  description = "Role Terraform uses for provisioning."
  type        = string
  default     = "ACCOUNTADMIN"
}

variable "database_name" {
  description = "Snowflake database for the POC."
  type        = string
  default     = "SF_UDP_POC"
}

variable "schema_names" {
  description = "Schemas to create in the POC database."
  type        = list(string)
  default     = ["RAW", "STAGING", "MARTS"]
}

variable "warehouse_name" {
  description = "Warehouse used by ingestion, dbt, and the dashboard."
  type        = string
  default     = "TRANSFORM_WH"
}

variable "transformer_role" {
  description = "Account role used by dbt and ingestion."
  type        = string
  default     = "TRANSFORMER"
}

variable "dbt_user_name" {
  description = "Snowflake service user name."
  type        = string
  default     = "DBT_USER"
}

variable "dbt_user_login_name" {
  description = "Snowflake service user login name."
  type        = string
  default     = "DBT_USER"
}

variable "dbt_user_password" {
  description = "Snowflake service user password. This is stored in Terraform state."
  type        = string
  sensitive   = true
}
