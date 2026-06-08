from __future__ import annotations

try:
    from .utils import (
        configure_logging,
        dataframe_from_records,
        fetch_socrata_records,
        get_snowflake_connection,
        load_dataframe,
        two_years_ago,
    )
except ImportError:
    from utils import (
        configure_logging,
        dataframe_from_records,
        fetch_socrata_records,
        get_snowflake_connection,
        load_dataframe,
        two_years_ago,
    )


API_URL = "https://data.sfgov.org/resource/i98e-djp9.json"
TABLE_NAME = "RAW_BUILDING_PERMITS"
MAX_ROWS = 50_000

COLUMNS = [
    "permit_number",
    "permit_type",
    "permit_creation_date",
    "status",
    "neighborhoods_analysis_boundaries",
    "supervisor_district",
    "estimated_cost",
    "street_name",
]


CREATE_TABLE_SQL = f"""
create table if not exists RAW.{TABLE_NAME} (
    permit_number varchar,
    permit_type varchar,
    permit_creation_date varchar,
    status varchar,
    neighborhoods_analysis_boundaries varchar,
    supervisor_district varchar,
    estimated_cost varchar,
    street_name varchar
)
"""


def main() -> None:
    configure_logging()
    records = fetch_socrata_records(
        url=API_URL,
        select_expressions=COLUMNS,
        date_field="permit_creation_date",
        since=two_years_ago(),
        max_rows=MAX_ROWS,
    )
    df = dataframe_from_records(records, COLUMNS)

    with get_snowflake_connection(schema="RAW") as conn:
        with conn.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)
            cursor.execute(f"truncate table RAW.{TABLE_NAME}")
        load_dataframe(conn, df, TABLE_NAME)


if __name__ == "__main__":
    main()
