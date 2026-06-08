from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from collections.abc import Iterable, Iterator

import pandas as pd
import requests
import snowflake.connector
from dotenv import load_dotenv
from snowflake.connector.pandas_tools import write_pandas


load_dotenv()

LOGGER = logging.getLogger("sf_city_pulse.ingestion")


def configure_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def get_env(name: str, default: str | None = None, required: bool = False) -> str | None:
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def two_years_ago() -> date:
    return date.today() - timedelta(days=730)


def get_snowflake_connection(schema: str = "RAW"):
    return snowflake.connector.connect(
        account=get_env("SNOWFLAKE_ACCOUNT", required=True),
        user=get_env("SNOWFLAKE_USER", required=True),
        password=get_env("SNOWFLAKE_PASSWORD", required=True),
        warehouse=get_env("SNOWFLAKE_WAREHOUSE", "TRANSFORM_WH"),
        database=get_env("SNOWFLAKE_DATABASE", "SF_UDP_POC"),
        schema=schema,
        role=get_env("SNOWFLAKE_ROLE", "TRANSFORMER"),
    )


def iter_socrata_batches(
    url: str,
    select_expressions: Iterable[str],
    date_field: str,
    since: date,
    max_rows: int | None = None,
    page_size: int = 50_000,
) -> Iterator[list[dict]]:
    app_token = get_env("SOCRATA_APP_TOKEN")
    headers = {"X-App-Token": app_token} if app_token else {}
    offset = 0
    total_records = 0

    while max_rows is None or total_records < max_rows:
        limit = page_size if max_rows is None else min(page_size, max_rows - total_records)
        params = {
            "$select": ",".join(select_expressions),
            "$where": f"{date_field} >= '{since.isoformat()}'",
            "$order": f"{date_field} ASC",
            "$limit": limit,
            "$offset": offset,
        }

        LOGGER.info("Fetching %s rows from %s at offset %s", limit, url, offset)
        response = requests.get(url, params=params, headers=headers, timeout=60)
        response.raise_for_status()
        batch = response.json()

        if not batch:
            break

        yield batch

        offset += len(batch)
        total_records += len(batch)

        if len(batch) < limit:
            break

    LOGGER.info("Fetched %s total records from %s", total_records, url)


def fetch_socrata_records(
    url: str,
    select_expressions: Iterable[str],
    date_field: str,
    since: date,
    max_rows: int | None = None,
    page_size: int = 50_000,
) -> list[dict]:
    records: list[dict] = []
    for batch in iter_socrata_batches(
        url=url,
        select_expressions=select_expressions,
        date_field=date_field,
        since=since,
        max_rows=max_rows,
        page_size=page_size,
    ):
        records.extend(batch)
    return records


def dataframe_from_records(records: list[dict], columns: list[str]) -> pd.DataFrame:
    df = pd.DataFrame.from_records(records)
    if df.empty:
        return pd.DataFrame(columns=[column.upper() for column in columns])

    df = df.reindex(columns=columns)
    df.columns = [column.upper() for column in columns]
    return df


def load_dataframe(
    conn,
    df: pd.DataFrame,
    table_name: str,
    schema: str = "RAW",
) -> int:
    if df.empty:
        LOGGER.warning("No rows to load into %s.%s", schema, table_name)
        return 0

    database = get_env("SNOWFLAKE_DATABASE", "SF_UDP_POC")
    success, chunks, rows, _ = write_pandas(
        conn=conn,
        df=df,
        table_name=table_name,
        database=database,
        schema=schema,
        quote_identifiers=False,
    )

    if not success:
        raise RuntimeError(f"write_pandas failed for {schema}.{table_name}")

    LOGGER.info("Loaded %s rows into %s.%s across %s chunk(s)", rows, schema, table_name, chunks)
    return rows
