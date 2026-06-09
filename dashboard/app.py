from __future__ import annotations

import logging
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import snowflake.connector
import streamlit as st
from dotenv import load_dotenv


load_dotenv()

LOGGER = logging.getLogger(__name__)
MART_NAME = "MART_NEIGHBORHOOD_EQUITY"


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


def get_mart_table() -> str:
    database = read_setting("SNOWFLAKE_DATABASE", "SF_UDP_POC")
    schema = read_setting("SNOWFLAKE_SCHEMA", "MARTS")
    return f"{database}.{schema}.{MART_NAME}"


def render_data_load_error(error: Exception) -> None:
    LOGGER.exception("Failed to load Snowflake mart")
    st.error("Could not load the Snowflake mart.")
    st.info(
        "Check Streamlit Cloud secrets. The hosted app should use DBT_USER with "
        "the TRANSFORMER role, not the ACCOUNTADMIN login."
    )
    with st.expander("Deployment context", expanded=True):
        st.code(
            "\n".join(
                [
                    f"account: {read_setting('SNOWFLAKE_ACCOUNT', 'missing')}",
                    f"user: {read_setting('SNOWFLAKE_USER', 'missing')}",
                    f"role: {read_setting('SNOWFLAKE_ROLE', 'TRANSFORMER')}",
                    f"warehouse: {read_setting('SNOWFLAKE_WAREHOUSE', 'TRANSFORM_WH')}",
                    f"database: {read_setting('SNOWFLAKE_DATABASE', 'SF_UDP_POC')}",
                    f"schema: {read_setting('SNOWFLAKE_SCHEMA', 'MARTS')}",
                    f"mart: {get_mart_table()}",
                    f"error_type: {type(error).__name__}",
                ]
            )
        )
    st.stop()


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
        from {get_mart_table()}
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


def weighted_average(values: pd.Series, weights: pd.Series) -> float:
    valid = values.notna() & weights.notna() & (weights > 0)
    if not valid.any():
        return float("nan")
    return float((values[valid] * weights[valid]).sum() / weights[valid].sum())


def aggregate_by_month(df: pd.DataFrame) -> pd.DataFrame:
    monthly = (
        df.groupby("month", as_index=False)
        .agg(
            total_311_requests=("total_311_requests", "sum"),
            total_permits=("total_permits", "sum"),
            active_permit_count=("active_permit_count", "sum"),
            open_request_count=("open_request_count", "sum"),
            total_estimated_cost=("total_estimated_cost", "sum"),
        )
        .sort_values("month")
    )
    avg_days = pd.DataFrame(
        [
            {
                "month": month,
                "avg_days_to_close": weighted_average(group["avg_days_to_close"], group["total_311_requests"]),
            }
            for month, group in df.groupby("month")
        ]
    )
    monthly = monthly.merge(avg_days, on="month", how="left")
    monthly["pct_open_requests"] = monthly["open_request_count"] / monthly["total_311_requests"].replace(0, pd.NA)
    monthly["construction_to_complaint_ratio"] = monthly["total_permits"] / monthly["total_311_requests"].replace(0, pd.NA)
    return monthly


def aggregate_by_neighborhood(df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        df.groupby(["neighborhood", "supervisor_district"], as_index=False)
        .agg(
            total_311_requests=("total_311_requests", "sum"),
            open_request_count=("open_request_count", "sum"),
            total_permits=("total_permits", "sum"),
            total_estimated_cost=("total_estimated_cost", "sum"),
            active_permit_count=("active_permit_count", "sum"),
            months_observed=("month", "nunique"),
        )
    )
    avg_days = pd.DataFrame(
        [
            {
                "neighborhood": neighborhood,
                "supervisor_district": supervisor_district,
                "avg_days_to_close": weighted_average(group["avg_days_to_close"], group["total_311_requests"]),
            }
            for (neighborhood, supervisor_district), group in df.groupby(["neighborhood", "supervisor_district"])
        ]
    )
    summary = summary.merge(avg_days, on=["neighborhood", "supervisor_district"], how="left")
    summary["pct_open_requests"] = summary["open_request_count"] / summary["total_311_requests"].replace(0, pd.NA)
    summary["construction_to_complaint_ratio"] = summary["total_permits"] / summary["total_311_requests"].replace(0, pd.NA)
    summary["estimated_cost_per_request"] = (
        summary["total_estimated_cost"] / summary["total_311_requests"].replace(0, pd.NA)
    )
    return summary


def aggregate_by_district(df: pd.DataFrame) -> pd.DataFrame:
    valid_districts = df.dropna(subset=["supervisor_district"])
    valid_districts = valid_districts[valid_districts["supervisor_district"].between(1, 11)]
    summary = (
        valid_districts.groupby("supervisor_district", as_index=False)
        .agg(
            total_311_requests=("total_311_requests", "sum"),
            open_request_count=("open_request_count", "sum"),
            total_permits=("total_permits", "sum"),
            active_permit_count=("active_permit_count", "sum"),
            total_estimated_cost=("total_estimated_cost", "sum"),
            neighborhoods=("neighborhood", "nunique"),
        )
    )
    avg_days = pd.DataFrame(
        [
            {
                "supervisor_district": supervisor_district,
                "avg_days_to_close": weighted_average(group["avg_days_to_close"], group["total_311_requests"]),
            }
            for supervisor_district, group in valid_districts.groupby("supervisor_district")
        ]
    )
    summary = summary.merge(avg_days, on="supervisor_district", how="left")
    summary["pct_open_requests"] = summary["open_request_count"] / summary["total_311_requests"].replace(0, pd.NA)
    return summary.sort_values("avg_days_to_close", ascending=False)


def city_overview(df: pd.DataFrame) -> None:
    total_requests = int(df["total_311_requests"].sum())
    avg_days = weighted_average(df["avg_days_to_close"], df["total_311_requests"])
    active_permits = int(df["active_permit_count"].sum())
    neighborhoods = df["neighborhood"].nunique()
    total_cost = df["total_estimated_cost"].sum()
    open_share = df["open_request_count"].sum() / max(total_requests, 1)

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total 311 requests", metric_value(total_requests))
    col2.metric("Avg days to close", metric_value(avg_days))
    col3.metric("Active permits", metric_value(active_permits))
    col4.metric("Neighborhoods", metric_value(neighborhoods))
    col5.metric("Open request share", metric_value(open_share * 100, "%"))

    monthly = aggregate_by_month(df)
    trend_fig = go.Figure()
    trend_fig.add_trace(
        go.Scatter(
            x=monthly["month"],
            y=monthly["total_311_requests"],
            name="311 requests",
            mode="lines+markers",
            yaxis="y",
        )
    )
    trend_fig.add_trace(
        go.Scatter(
            x=monthly["month"],
            y=monthly["total_permits"],
            name="Permits",
            mode="lines+markers",
            yaxis="y2",
        )
    )
    trend_fig.update_layout(
        title="Monthly activity trend",
        height=420,
        yaxis={"title": "311 requests"},
        yaxis2={"title": "Permits", "overlaying": "y", "side": "right"},
        legend={"orientation": "h"},
    )
    st.plotly_chart(trend_fig, use_container_width=True)

    col_left, col_right = st.columns([1.05, 0.95])
    neighborhood_summary = aggregate_by_neighborhood(df)
    top_neighborhoods = neighborhood_summary.sort_values("total_311_requests", ascending=False).head(12)
    fig = px.bar(
        top_neighborhoods,
        x="total_311_requests",
        y="neighborhood",
        orientation="h",
        labels={"total_311_requests": "311 requests", "neighborhood": "Neighborhood"},
        title="Top neighborhoods by 311 volume",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=460)
    col_left.plotly_chart(fig, use_container_width=True)

    high_response_time = (
        neighborhood_summary[neighborhood_summary["total_311_requests"] >= 500]
        .sort_values("avg_days_to_close", ascending=False)
        .head(12)
    )
    high_response_time_display = high_response_time.copy()
    high_response_time_display["pct_open_requests"] = high_response_time_display["pct_open_requests"] * 100
    col_right.dataframe(
        high_response_time_display[
            [
                "neighborhood",
                "supervisor_district",
                "total_311_requests",
                "avg_days_to_close",
                "pct_open_requests",
                "total_permits",
            ]
        ],
        use_container_width=True,
        hide_index=True,
        column_config={
            "neighborhood": "Neighborhood",
            "supervisor_district": "District",
            "total_311_requests": st.column_config.NumberColumn("311 requests", format="%d"),
            "avg_days_to_close": st.column_config.NumberColumn("Avg days", format="%.2f"),
            "pct_open_requests": st.column_config.ProgressColumn("Open share", format="%.1f%%", min_value=0, max_value=100),
            "total_permits": st.column_config.NumberColumn("Permits", format="%d"),
        },
    )
    st.caption(f"Estimated construction value in selected period: ${total_cost:,.0f}")


def equity_view(df: pd.DataFrame) -> None:
    district_summary = aggregate_by_district(df)
    city_avg = weighted_average(df["avg_days_to_close"], df["total_311_requests"])
    district_summary["city_avg_days_to_close"] = city_avg
    district_summary["response_index"] = district_summary["avg_days_to_close"] / city_avg
    district_summary["response_time_flag"] = district_summary["avg_days_to_close"].apply(
        lambda value: "Above 2x city avg" if pd.notna(value) and value > city_avg * 2 else "Within range"
    )

    selected_district = st.selectbox(
        "District detail",
        options=district_summary["supervisor_district"].astype(int).tolist(),
        index=0,
    )

    col_heatmap, col_trend = st.columns([0.95, 1.05])
    fig = px.bar(
        district_summary.sort_values("avg_days_to_close", ascending=True),
        x="avg_days_to_close",
        y=district_summary.sort_values("avg_days_to_close", ascending=True)["supervisor_district"].astype(str),
        orientation="h",
        color="response_index",
        color_continuous_scale="Reds",
        labels={
            "avg_days_to_close": "Avg days to close",
            "y": "Supervisor district",
            "response_index": "Response index",
        },
        title="District response time index",
    )
    fig.add_vline(x=city_avg, line_dash="dash", line_color="#202124")
    fig.update_layout(height=430)
    col_heatmap.plotly_chart(fig, use_container_width=True)

    monthly = aggregate_by_month(df)
    district_monthly = aggregate_by_month(df[df["supervisor_district"] == selected_district])
    trend_fig = go.Figure()
    trend_fig.add_trace(
        go.Scatter(x=monthly["month"], y=monthly["avg_days_to_close"], name="City avg", mode="lines+markers")
    )
    trend_fig.add_trace(
        go.Scatter(
            x=district_monthly["month"],
            y=district_monthly["avg_days_to_close"],
            name=f"District {selected_district}",
            mode="lines+markers",
        )
    )
    trend_fig.update_layout(
        title=f"District {selected_district} monthly response time",
        yaxis_title="Avg days to close",
        height=430,
        legend={"orientation": "h"},
    )
    col_trend.plotly_chart(trend_fig, use_container_width=True)

    district_summary_display = district_summary.copy()
    district_summary_display["pct_open_requests"] = district_summary_display["pct_open_requests"] * 100
    st.dataframe(
        district_summary_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "supervisor_district": "District",
            "avg_days_to_close": st.column_config.NumberColumn("Avg days to close", format="%.2f"),
            "city_avg_days_to_close": st.column_config.NumberColumn("City avg", format="%.2f"),
            "response_index": st.column_config.NumberColumn("Response index", format="%.2f"),
            "total_311_requests": st.column_config.NumberColumn("311 requests", format="%d"),
            "active_permit_count": st.column_config.NumberColumn("Active permits", format="%d"),
            "pct_open_requests": st.column_config.ProgressColumn("Open share", format="%.1f%%", min_value=0, max_value=100),
            "neighborhoods": st.column_config.NumberColumn("Neighborhoods", format="%d"),
            "response_time_flag": "Equity flag",
        },
    )


def construction_vs_complaints(df: pd.DataFrame) -> None:
    minimum_requests = st.slider("Minimum 311 requests for rankings", 0, 5_000, 100, step=100)
    neighborhood_summary = aggregate_by_neighborhood(df).query("total_permits > 0 or total_311_requests > 0")
    ranked = neighborhood_summary[neighborhood_summary["total_311_requests"] >= minimum_requests]

    fig = px.scatter(
        ranked,
        x="total_permits",
        y="total_311_requests",
        color="supervisor_district",
        size="total_estimated_cost",
        hover_name="neighborhood",
        hover_data={
            "avg_days_to_close": ":.2f",
            "active_permit_count": True,
            "construction_to_complaint_ratio": ":.3f",
            "total_estimated_cost": ":,.0f",
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

    col_ratio, col_cost = st.columns(2)
    ratio_leaders = ranked.sort_values("construction_to_complaint_ratio", ascending=False).head(12)
    cost_leaders = ranked.sort_values("total_estimated_cost", ascending=False).head(12)
    table_columns = [
        "neighborhood",
        "supervisor_district",
        "total_permits",
        "total_311_requests",
        "construction_to_complaint_ratio",
        "total_estimated_cost",
        "avg_days_to_close",
    ]
    column_config = {
        "neighborhood": "Neighborhood",
        "supervisor_district": "District",
        "total_permits": st.column_config.NumberColumn("Permits", format="%d"),
        "total_311_requests": st.column_config.NumberColumn("311 requests", format="%d"),
        "construction_to_complaint_ratio": st.column_config.NumberColumn("Permit/request", format="%.3f"),
        "total_estimated_cost": st.column_config.NumberColumn("Estimated cost", format="$%.0f"),
        "avg_days_to_close": st.column_config.NumberColumn("Avg days", format="%.2f"),
    }
    col_ratio.dataframe(
        ratio_leaders[table_columns],
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
    )
    col_cost.dataframe(
        cost_leaders[table_columns],
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
    )


def neighborhood_drilldown(df: pd.DataFrame) -> None:
    neighborhood_summary = aggregate_by_neighborhood(df)
    neighborhoods = sorted(neighborhood_summary["neighborhood"].dropna().unique())
    default_index = neighborhoods.index("Mission") if "Mission" in neighborhoods else 0
    selected_neighborhood = st.selectbox("Neighborhood", neighborhoods, index=default_index)

    selected = df[df["neighborhood"] == selected_neighborhood]
    summary = aggregate_by_neighborhood(selected).sort_values("total_311_requests", ascending=False)
    monthly = aggregate_by_month(selected)

    total_requests = int(summary["total_311_requests"].sum())
    avg_days = weighted_average(summary["avg_days_to_close"], summary["total_311_requests"])
    total_permits = int(summary["total_permits"].sum())
    total_cost = summary["total_estimated_cost"].sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("311 requests", metric_value(total_requests))
    col2.metric("Avg days to close", metric_value(avg_days))
    col3.metric("Permits", metric_value(total_permits))
    col4.metric("Estimated cost", f"${total_cost:,.0f}")

    trend_fig = go.Figure()
    trend_fig.add_trace(
        go.Scatter(x=monthly["month"], y=monthly["total_311_requests"], name="311 requests", mode="lines+markers")
    )
    trend_fig.add_trace(
        go.Scatter(x=monthly["month"], y=monthly["total_permits"], name="Permits", mode="lines+markers", yaxis="y2")
    )
    trend_fig.add_trace(
        go.Scatter(
            x=monthly["month"],
            y=monthly["avg_days_to_close"],
            name="Avg days",
            mode="lines+markers",
            yaxis="y3",
        )
    )
    trend_fig.update_layout(
        title=f"{selected_neighborhood} monthly profile",
        height=470,
        yaxis={"title": "311 requests"},
        yaxis2={"title": "Permits", "overlaying": "y", "side": "right"},
        yaxis3={
            "title": "Avg days",
            "anchor": "free",
            "overlaying": "y",
            "side": "right",
            "position": 0.94,
        },
        legend={"orientation": "h"},
    )
    st.plotly_chart(trend_fig, use_container_width=True)

    district_breakdown = summary[
        [
            "supervisor_district",
            "total_311_requests",
            "open_request_count",
            "pct_open_requests",
            "total_permits",
            "active_permit_count",
            "total_estimated_cost",
            "avg_days_to_close",
            "construction_to_complaint_ratio",
        ]
    ]
    district_breakdown = district_breakdown.copy()
    district_breakdown["pct_open_requests"] = district_breakdown["pct_open_requests"] * 100
    st.dataframe(
        district_breakdown,
        use_container_width=True,
        hide_index=True,
        column_config={
            "supervisor_district": "District",
            "total_311_requests": st.column_config.NumberColumn("311 requests", format="%d"),
            "open_request_count": st.column_config.NumberColumn("Open requests", format="%d"),
            "pct_open_requests": st.column_config.ProgressColumn("Open share", format="%.1f%%", min_value=0, max_value=100),
            "total_permits": st.column_config.NumberColumn("Permits", format="%d"),
            "active_permit_count": st.column_config.NumberColumn("Active permits", format="%d"),
            "total_estimated_cost": st.column_config.NumberColumn("Estimated cost", format="$%.0f"),
            "avg_days_to_close": st.column_config.NumberColumn("Avg days", format="%.2f"),
            "construction_to_complaint_ratio": st.column_config.NumberColumn("Permit/request", format="%.3f"),
        },
    )


def main() -> None:
    st.set_page_config(page_title="SF City Pulse", page_icon="SF", layout="wide")
    st.title("SF City Pulse")
    st.caption("311 response equity and construction activity across San Francisco neighborhoods")

    try:
        df = load_data()
    except Exception as error:
        render_data_load_error(error)

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

    valid_districts = sorted(
        int(value)
        for value in filtered["supervisor_district"].dropna().unique()
        if 1 <= int(value) <= 11
    )
    selected_districts = st.multiselect(
        "Supervisor districts",
        options=valid_districts,
        default=valid_districts,
    )
    if selected_districts:
        filtered = filtered[filtered["supervisor_district"].isin(selected_districts)]

    tab_overview, tab_equity, tab_construction, tab_neighborhood = st.tabs(
        ["City Overview", "District Equity", "Construction vs Complaints", "Neighborhood Drilldown"]
    )

    with tab_overview:
        city_overview(filtered)
    with tab_equity:
        equity_view(filtered)
    with tab_construction:
        construction_vs_complaints(filtered)
    with tab_neighborhood:
        neighborhood_drilldown(filtered)


if __name__ == "__main__":
    main()
