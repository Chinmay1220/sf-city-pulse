from __future__ import annotations

import os

import snowflake.connector
from dotenv import load_dotenv


load_dotenv()


def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def main() -> None:
    database = env("SNOWFLAKE_DATABASE", "SF_UDP_POC")
    warehouse = env("SNOWFLAKE_WAREHOUSE", "TRANSFORM_WH")
    role = env("SNOWFLAKE_ROLE", "TRANSFORMER")
    dbt_user = env("SNOWFLAKE_USER", "DBT_USER")
    dbt_password = env("TF_VAR_dbt_user_password")

    conn = snowflake.connector.connect(
        account=env("SNOWFLAKE_ACCOUNT"),
        user=env("TF_VAR_snowflake_user"),
        password=env("TF_VAR_snowflake_password"),
        role=env("TF_VAR_snowflake_admin_role", "ACCOUNTADMIN"),
    )

    statements = [
        "use role ACCOUNTADMIN",
        f"create database if not exists {database}",
        f"create schema if not exists {database}.RAW",
        f"create schema if not exists {database}.STAGING",
        f"create schema if not exists {database}.MARTS",
        (
            f"create warehouse if not exists {warehouse} "
            "warehouse_size = XSMALL "
            "auto_suspend = 60 "
            "auto_resume = true "
            "initially_suspended = true"
        ),
        f"create role if not exists {role}",
        (
            f"create user if not exists {dbt_user} "
            f"password = {quote_literal(dbt_password)} "
            f"default_role = {role} "
            f"default_warehouse = {warehouse} "
            f"default_namespace = {database}.MARTS "
            "must_change_password = false"
        ),
        (
            f"alter user {dbt_user} set "
            f"default_role = {role} "
            f"default_warehouse = {warehouse} "
            f"default_namespace = {database}.MARTS"
        ),
        f"grant role {role} to user {dbt_user}",
        f"grant usage, operate on warehouse {warehouse} to role {role}",
        f"grant usage, create schema on database {database} to role {role}",
    ]

    for schema in ("RAW", "STAGING", "MARTS"):
        qualified_schema = f"{database}.{schema}"
        statements.extend(
            [
                f"grant usage on schema {qualified_schema} to role {role}",
                (
                    f"grant create table, create view, create stage, create file format "
                    f"on schema {qualified_schema} to role {role}"
                ),
                f"grant select on future tables in schema {qualified_schema} to role {role}",
                f"grant select on future views in schema {qualified_schema} to role {role}",
            ]
        )

    with conn:
        with conn.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)

    print(f"Provisioned {database}, {warehouse}, role {role}, and user {dbt_user}.")


if __name__ == "__main__":
    main()
