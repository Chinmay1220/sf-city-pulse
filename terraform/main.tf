terraform {
  required_version = ">= 1.5.0"

  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "= 2.0.0"
    }
  }
}

provider "snowflake" {
  organization_name = var.snowflake_organization_name
  account_name      = var.snowflake_account_name
  user              = var.snowflake_user
  password          = var.snowflake_password
  role              = var.snowflake_admin_role
}

resource "snowflake_database" "sf_udp_poc" {
  name    = var.database_name
  comment = "Unified Data Platform POC for San Francisco open data."
}

resource "snowflake_schema" "schemas" {
  for_each = toset(var.schema_names)

  database = snowflake_database.sf_udp_poc.name
  name     = each.value
  comment  = "SF UDP POC ${each.value} schema."
}

resource "snowflake_warehouse" "transform_wh" {
  name                = var.warehouse_name
  warehouse_size      = "XSMALL"
  auto_suspend        = 60
  auto_resume         = true
  initially_suspended = true
  comment             = "Small warehouse for ingestion, dbt transforms, and dashboard reads."
}

resource "snowflake_account_role" "transformer" {
  name    = var.transformer_role
  comment = "Runs ingestion, dbt transforms, and Streamlit dashboard queries for the SF UDP POC."
}

resource "snowflake_legacy_service_user" "dbt_user" {
  name              = var.dbt_user_name
  login_name        = var.dbt_user_login_name
  password          = var.dbt_user_password
  disabled          = "false"
  display_name      = "SF UDP POC dbt service user"
  comment           = "Legacy service user for local POC password-based dbt and Python connector flows."
  default_role      = snowflake_account_role.transformer.name
  default_warehouse = snowflake_warehouse.transform_wh.name
  default_namespace = "${snowflake_database.sf_udp_poc.name}.${snowflake_schema.schemas["MARTS"].name}"
}

resource "snowflake_grant_account_role" "grant_transformer_to_dbt_user" {
  role_name = snowflake_account_role.transformer.name
  user_name = snowflake_legacy_service_user.dbt_user.name
}

resource "snowflake_grant_privileges_to_account_role" "warehouse_usage" {
  privileges        = ["USAGE", "OPERATE"]
  account_role_name = snowflake_account_role.transformer.name

  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.transform_wh.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "database_usage" {
  privileges        = ["USAGE", "CREATE SCHEMA"]
  account_role_name = snowflake_account_role.transformer.name

  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.sf_udp_poc.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "schema_build" {
  for_each = snowflake_schema.schemas

  privileges = [
    "USAGE",
    "CREATE TABLE",
    "CREATE VIEW",
    "CREATE STAGE",
    "CREATE FILE FORMAT"
  ]

  account_role_name = snowflake_account_role.transformer.name

  on_schema {
    schema_name = each.value.fully_qualified_name
  }
}
