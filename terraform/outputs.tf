output "database_name" {
  value = snowflake_database.sf_udp_poc.name
}

output "schema_names" {
  value = [for schema in snowflake_schema.schemas : schema.name]
}

output "warehouse_name" {
  value = snowflake_warehouse.transform_wh.name
}

output "transformer_role" {
  value = snowflake_account_role.transformer.name
}

output "dbt_user_name" {
  value = snowflake_legacy_service_user.dbt_user.name
}
