from __future__ import annotations

try:
    from .utils import (
        configure_logging,
        dataframe_from_records,
        get_snowflake_connection,
        iter_socrata_batches,
        load_dataframe,
        two_years_ago,
    )
except ImportError:
    from utils import (
        configure_logging,
        dataframe_from_records,
        get_snowflake_connection,
        iter_socrata_batches,
        load_dataframe,
        two_years_ago,
    )


API_URL = "https://data.sfgov.org/resource/vw6y-z8j6.json"
TABLE_NAME = "RAW_311_REQUESTS"
MAX_ROWS = None
PAGE_SIZE = 50_000

COLUMNS = [
    "service_request_id",
    "requested_datetime",
    "closed_date",
    "status_description",
    "service_name",
    "supervisor_district",
    "neighborhood",
    "lat",
    "long",
]

SELECT_EXPRESSIONS = [
    "service_request_id",
    "requested_datetime",
    "closed_date",
    "status_description",
    "service_name",
    "supervisor_district",
    "neighborhoods_sffind_boundaries as neighborhood",
    "lat",
    "long",
]


CREATE_TABLE_SQL = f"""
create table if not exists RAW.{TABLE_NAME} (
    service_request_id varchar,
    requested_datetime varchar,
    closed_date varchar,
    status_description varchar,
    service_name varchar,
    supervisor_district varchar,
    neighborhood varchar,
    lat varchar,
    "LONG" varchar
)
"""


def main() -> None:
    configure_logging()
    with get_snowflake_connection(schema="RAW") as conn:
        with conn.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)
            cursor.execute(f"truncate table RAW.{TABLE_NAME}")

        total_rows = 0
        for records in iter_socrata_batches(
            url=API_URL,
            select_expressions=SELECT_EXPRESSIONS,
            date_field="requested_datetime",
            since=two_years_ago(),
            max_rows=MAX_ROWS,
            page_size=PAGE_SIZE,
        ):
            df = dataframe_from_records(records, COLUMNS)
            total_rows += load_dataframe(conn, df, TABLE_NAME)

        print(f"Loaded {total_rows} total rows into RAW.{TABLE_NAME}")


if __name__ == "__main__":
    main()
