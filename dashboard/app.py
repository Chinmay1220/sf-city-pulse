from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import snowflake.connector
import streamlit as st
from dotenv import load_dotenv


load_dotenv()

MART_TABLE = "MARTS.MART_NEIGHBORHOOD_EQUITY"


def read_setting(name: str, default: str | None = None) -> str | None:
    try:
        snowflake_secrets = st.secrets.get("snowflake", {})
    except Exception:
        snowflake_secrets = {}

    if name.lower() in snowflake_secrets:
        return snowflake_secrets[name.lower()]
    return os.getenv(name, default)


def get_connection():
    required = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD"]
    missing = [name for name in required if not read_setting(name)]
    if missing:
        st.error(f"Missing Snowflake settings: {', '.join(missing)}")
        st.stop()

    return snowflake.connector.connect(
        account=read_setting("SNOWFLAKE_ACCOUNT"),
        user=read_setting("SNOWFLAKE_USER"),
        password=read_setting("SNOWFLAKE_PASSWORD"),
        warehouse=read_setting("SNOWFLAKE_WAREHOUSE", "TRANSFORM_WH"),
        database=read_setting("SNOWFLAKE_DATABASE", "SF_UDP_POC"),
        schema=read_setting("SNOWFLAKE_SCHEMA", "MARTS"),
        role=read_setting("SNOWFLAKE_ROLE", "TRANSFORMER"),
    )


@st.cache_data(ttl=600)
def load_data() -> pd.DataFrame:
    query = f"""
        select
            neighborhood,
            supervisor_district,
            month,
            total_311_requests,
            avg_days_to_close,
            open_request_count,
            pct_open_requests,
            total_permits,
            total_estimated_cost,
            active_permit_count,
            construction_to_complaint_ratio
        from {MART_TABLE}
    """
    with get_connection() as conn:
        df = pd.read_sql(query, conn)

    df.columns = [column.lower() for column in df.columns]
    df["month"] = pd.to_datetime(df["month"])
    return df


def metric_value(value: float | int | None, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "n/a"
    if isinstance(value, float):
        return f"{value:,.1f}{suffix}"
    return f"{value:,}{suffix}"


def city_overview(df: pd.DataFrame) -> None:
    total_requests = int(df["total_311_requests"].sum())
    avg_days = df.loc[df["avg_days_to_close"].notna(), "avg_days_to_close"].mean()
    active_permits = int(df["active_permit_count"].sum())

    col1, col2, col3 = st.columns(3)
    col1.metric("Total 311 requests", metric_value(total_requests))
    col2.metric("Avg days to close", metric_value(avg_days))
    col3.metric("Active permits", metric_value(active_permits))

    top_neighborhoods = (
        df.groupby("neighborhood", as_index=False)["total_311_requests"]
        .sum()
        .sort_values("total_311_requests", ascending=False)
        .head(10)
    )
    fig = px.bar(
        top_neighborhoods,
        x="total_311_requests",
        y="neighborhood",
        orientation="h",
        labels={"total_311_requests": "311 requests", "neighborhood": "Neighborhood"},
        title="Top 10 neighborhoods by 311 volume",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=460)
    st.plotly_chart(fig, use_container_width=True)


def equity_view(df: pd.DataFrame) -> None:
    district_summary = (
        df.dropna(subset=["supervisor_district"])
        .groupby("supervisor_district", as_index=False)
        .agg(
            avg_days_to_close=("avg_days_to_close", "mean"),
            total_311_requests=("total_311_requests", "sum"),
            active_permit_count=("active_permit_count", "sum"),
        )
        .sort_values("avg_days_to_close", ascending=False)
    )
    city_avg = df["avg_days_to_close"].mean()
    district_summary["city_avg_days_to_close"] = city_avg
    district_summary["response_time_flag"] = district_summary["avg_days_to_close"].apply(
        lambda value: "Above 2x city avg" if pd.notna(value) and value > city_avg * 2 else "Within range"
    )

    fig = px.imshow(
        district_summary[["avg_days_to_close"]].T,
        x=district_summary["supervisor_district"].astype(str),
        y=["Avg days to close"],
        color_continuous_scale="Reds",
        labels={"x": "Supervisor district", "color": "Days"},
        aspect="auto",
        title="Response time by supervisor district",
    )
    fig.update_layout(height=260)
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        district_summary,
        use_container_width=True,
        hide_index=True,
        column_config={
            "supervisor_district": "District",
            "avg_days_to_close": st.column_config.NumberColumn("Avg days to close", format="%.2f"),
            "city_avg_days_to_close": st.column_config.NumberColumn("City avg", format="%.2f"),
            "total_311_requests": st.column_config.NumberColumn("311 requests", format="%d"),
            "active_permit_count": st.column_config.NumberColumn("Active permits", format="%d"),
            "response_time_flag": "Equity flag",
        },
    )


def construction_vs_complaints(df: pd.DataFrame) -> None:
    neighborhood_summary = (
        df.groupby(["neighborhood", "supervisor_district"], as_index=False)
        .agg(
            total_permits=("total_permits", "sum"),
            total_311_requests=("total_311_requests", "sum"),
            avg_days_to_close=("avg_days_to_close", "mean"),
            active_permit_count=("active_permit_count", "sum"),
        )
        .query("total_permits > 0 or total_311_requests > 0")
    )

    fig = px.scatter(
        neighborhood_summary,
        x="total_permits",
        y="total_311_requests",
        color="supervisor_district",
        size="active_permit_count",
        hover_name="neighborhood",
        hover_data={
            "avg_days_to_close": ":.2f",
            "active_permit_count": True,
            "supervisor_district": True,
        },
        labels={
            "total_permits": "Total permits",
            "total_311_requests": "Total 311 requests",
            "supervisor_district": "District",
        },
        title="Construction activity versus 311 complaints",
    )
    fig.update_layout(height=560)
    st.plotly_chart(fig, use_container_width=True)

    high_construction = neighborhood_summary.sort_values(
        ["total_permits", "avg_days_to_close"],
        ascending=[False, False],
    ).head(8)
    st.dataframe(
        high_construction,
        use_container_width=True,
        hide_index=True,
        column_config={
            "neighborhood": "Neighborhood",
            "supervisor_district": "District",
            "total_permits": st.column_config.NumberColumn("Permits", format="%d"),
            "total_311_requests": st.column_config.NumberColumn("311 requests", format="%d"),
            "avg_days_to_close": st.column_config.NumberColumn("Avg days to close", format="%.2f"),
            "active_permit_count": st.column_config.NumberColumn("Active permits", format="%d"),
        },
    )


def main() -> None:
    st.set_page_config(page_title="SF City Pulse", page_icon="SF", layout="wide")
    st.title("SF City Pulse")
    st.caption("311 response equity and construction activity across San Francisco neighborhoods")

    df = load_data()
    if df.empty:
        st.warning("No mart rows found. Run ingestion and dbt before opening the dashboard.")
        st.stop()

    min_month = df["month"].min().date()
    max_month = df["month"].max().date()
    selected_months = st.slider(
        "Month range",
        min_value=min_month,
        max_value=max_month,
        value=(min_month, max_month),
        format="YYYY-MM",
    )
    filtered = df[
        (df["month"].dt.date >= selected_months[0])
        & (df["month"].dt.date <= selected_months[1])
    ]

    tab_overview, tab_equity, tab_construction = st.tabs(
        ["City Overview", "Neighborhood Equity Map", "Construction vs Complaints"]
    )

    with tab_overview:
        city_overview(filtered)
    with tab_equity:
        equity_view(filtered)
    with tab_construction:
        construction_vs_complaints(filtered)


if __name__ == "__main__":
    main()
