"""Render a polished README dashboard preview from the local BI extract."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".tmp-matplotlib"))

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import FuncFormatter


CSV_PATH = ROOT / "bi" / "sf_city_pulse_powerbi_extract.csv"
OUTPUT_PATH = ROOT / "docs" / "assets" / "sf-city-pulse-dashboard.png"
EQUITY_OUTPUT_PATH = ROOT / "docs" / "assets" / "sf-city-pulse-dashboard-equity.png"
CONSTRUCTION_OUTPUT_PATH = ROOT / "docs" / "assets" / "sf-city-pulse-dashboard-construction.png"
NEIGHBORHOOD_OUTPUT_PATH = ROOT / "docs" / "assets" / "sf-city-pulse-dashboard-neighborhood.png"

BG = "#f7f8fb"
PANEL = "#ffffff"
INK = "#111827"
MUTED = "#64748b"
GRID = "#e5e7eb"
BLUE = "#2563eb"
TEAL = "#0f766e"
CORAL = "#f97316"
GOLD = "#ca8a04"
RED = "#dc2626"
BORDER = "#d9e2ec"


def compact_number(value: float, prefix: str = "") -> str:
    value = float(value)
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        return f"{prefix}{value / 1_000_000_000:.1f}B"
    if abs_value >= 1_000_000:
        return f"{prefix}{value / 1_000_000:.1f}M"
    if abs_value >= 1_000:
        return f"{prefix}{value / 1_000:.1f}K"
    return f"{prefix}{value:,.0f}"


def add_panel(ax, radius: float = 0.035) -> None:
    box = FancyBboxPatch(
        (0, 0),
        1,
        1,
        transform=ax.transAxes,
        boxstyle=f"round,pad=0.018,rounding_size={radius}",
        linewidth=1.1,
        edgecolor=BORDER,
        facecolor=PANEL,
        clip_on=False,
        zorder=-10,
    )
    ax.add_patch(box)
    ax.set_facecolor("none")


def clean_axis(ax) -> None:
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(True, axis="y", color=GRID, linewidth=0.8, alpha=0.8)


def make_panel(fig, rect: list[float], title: str, subtitle: str | None = None):
    panel = fig.add_axes(rect)
    add_panel(panel)
    panel.axis("off")
    panel.text(0.045, 0.92, title, transform=panel.transAxes, fontsize=13.5, fontweight="bold", color=INK)
    if subtitle:
        panel.text(0.045, 0.84, subtitle, transform=panel.transAxes, fontsize=8.8, color=MUTED)
    return panel


def k_formatter(value: float, _pos: int) -> str:
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.0f}K"
    return f"{value:.0f}"


def short_label(value: str, max_chars: int = 18) -> str:
    replacements = {
        "Financial District/South Beach": "Financial District",
        "Bayview Hunters Point": "Bayview HP",
        "West Of Twin Peaks": "West Twin Peaks",
        "South Of Market": "SoMa",
    }
    label = replacements.get(value, value)
    if len(label) <= max_chars:
        return label
    return f"{label[: max_chars - 1]}..."


def base_figure(title: str, subtitle: str, badge: str) -> plt.Figure:
    fig = plt.figure(figsize=(16, 9), dpi=160, facecolor=BG)
    fig.text(0.045, 0.94, title, fontsize=30, fontweight="bold", color=INK)
    fig.text(0.045, 0.905, subtitle, fontsize=13, color=MUTED)
    fig.text(0.955, 0.935, "Snowflake  |  dbt  |  Streamlit  |  Power BI", fontsize=11, color=MUTED, ha="right")
    fig.text(0.955, 0.905, badge, fontsize=9.5, color=TEAL, ha="right", fontweight="bold")
    return fig


def add_kpi(fig: plt.Figure, index: int, label: str, value: str, note: str, color: str) -> None:
    ax = fig.add_axes([0.045 + index * 0.235, 0.735, 0.205, 0.12])
    add_panel(ax)
    ax.axis("off")
    ax.text(0.07, 0.75, label.upper(), transform=ax.transAxes, fontsize=8.5, color=MUTED, fontweight="bold")
    value_size = 25 if len(value) <= 8 else 20 if len(value) <= 14 else 16
    ax.text(0.07, 0.37, value, transform=ax.transAxes, fontsize=value_size, color=INK, fontweight="bold")
    ax.text(0.07, 0.14, note, transform=ax.transAxes, fontsize=8.7, color=MUTED)
    ax.plot([0.72, 0.92], [0.78, 0.78], transform=ax.transAxes, color=color, linewidth=4.5, solid_capstyle="round")
    ax.plot([0.72, 0.92], [0.66, 0.66], transform=ax.transAxes, color=color, linewidth=4.5, alpha=0.35, solid_capstyle="round")


def weighted_average(values: pd.Series, weights: pd.Series) -> float:
    valid = values.notna() & weights.notna() & (weights > 0)
    if not valid.any():
        return float("nan")
    return float((values[valid] * weights[valid]).sum() / weights[valid].sum())


def render_equity_dashboard(df: pd.DataFrame, output_path: Path) -> None:
    district = (
        df[df["DISTRICT_LABEL"] != "Unassigned"]
        .groupby("DISTRICT_LABEL", as_index=False)
        .agg(
            total_requests=("TOTAL_311_REQUESTS", "sum"),
            open_requests=("OPEN_REQUEST_COUNT", "sum"),
            avg_days=("AVG_DAYS_TO_CLOSE", "mean"),
            neighborhoods=("NEIGHBORHOOD", "nunique"),
        )
        .assign(open_share=lambda data: data["open_requests"] / data["total_requests"])
    )
    city_avg = weighted_average(df["AVG_DAYS_TO_CLOSE"], df["TOTAL_311_REQUESTS"])
    district["response_index"] = district["avg_days"] / city_avg
    district = district.sort_values("response_index", ascending=False)
    slowest_district = district.iloc[0]
    highest_open = district.sort_values("open_share", ascending=False).iloc[0]

    selected_district = slowest_district["DISTRICT_LABEL"]
    city_monthly = (
        df.groupby("MONTH_START_DATE", as_index=False)
        .agg(total_requests=("TOTAL_311_REQUESTS", "sum"), avg_days=("AVG_DAYS_TO_CLOSE", "mean"))
        .sort_values("MONTH_START_DATE")
    )
    district_monthly = (
        df[df["DISTRICT_LABEL"] == selected_district]
        .groupby("MONTH_START_DATE", as_index=False)
        .agg(avg_days=("AVG_DAYS_TO_CLOSE", "mean"))
        .sort_values("MONTH_START_DATE")
    )

    fig = base_figure(
        "District Equity Dashboard",
        "Response-time index, open-request share, and district-level service pressure",
        "Sorted district performance view",
    )
    add_kpi(fig, 0, "City Avg. Days", f"{city_avg:.1f}", "Weighted by request volume", BLUE)
    add_kpi(fig, 1, "Slowest District", selected_district.replace("District ", "D"), f"{slowest_district['avg_days']:.1f} avg days", RED)
    add_kpi(fig, 2, "Highest Open Share", highest_open["DISTRICT_LABEL"].replace("District ", "D"), f"{highest_open['open_share']:.1%} open", CORAL)
    add_kpi(fig, 3, "Districts", f"{len(district)}", "Valid supervisor districts", TEAL)

    bar_panel = make_panel(fig, [0.045, 0.365, 0.43, 0.31], "Response Index by District", "1.00 equals city average")
    ax_bar = bar_panel.inset_axes([0.1, 0.13, 0.84, 0.68])
    sorted_bar = district.sort_values("response_index")
    y_positions = range(len(sorted_bar))
    ax_bar.barh(y_positions, sorted_bar["response_index"], color=TEAL, alpha=0.92)
    ax_bar.set_yticks(list(y_positions), sorted_bar["DISTRICT_LABEL"])
    ax_bar.axvline(1, color=RED, linewidth=1.6, linestyle="--")
    ax_bar.set_xlim(0, max(sorted_bar["response_index"].max() * 1.2, 1.4))
    ax_bar.set_xlabel("Response index", color=MUTED, fontsize=8.5)
    clean_axis(ax_bar)

    trend_panel = make_panel(fig, [0.505, 0.365, 0.45, 0.31], f"{selected_district} vs City", "Monthly average closure time")
    ax_trend = trend_panel.inset_axes([0.08, 0.16, 0.86, 0.65])
    ax_trend.plot(city_monthly["MONTH_START_DATE"], city_monthly["avg_days"], color=BLUE, linewidth=2.4, label="City")
    ax_trend.plot(district_monthly["MONTH_START_DATE"], district_monthly["avg_days"], color=RED, linewidth=2.4, label=selected_district)
    ax_trend.legend(frameon=False, fontsize=8, loc="upper left")
    ax_trend.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax_trend.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
    ax_trend.set_ylabel("Avg days", color=MUTED, fontsize=8.5)
    clean_axis(ax_trend)

    table_panel = make_panel(fig, [0.045, 0.095, 0.91, 0.21], "District Watchlist", "Sorted by response index, then open-request share")
    table_panel.text(0.04, 0.65, "District", transform=table_panel.transAxes, fontsize=8.5, color=MUTED, fontweight="bold")
    table_panel.text(0.25, 0.65, "Requests", transform=table_panel.transAxes, fontsize=8.5, color=MUTED, fontweight="bold")
    table_panel.text(0.43, 0.65, "Avg Days", transform=table_panel.transAxes, fontsize=8.5, color=MUTED, fontweight="bold")
    table_panel.text(0.6, 0.65, "Response Index", transform=table_panel.transAxes, fontsize=8.5, color=MUTED, fontweight="bold")
    table_panel.text(0.8, 0.65, "Open Share", transform=table_panel.transAxes, fontsize=8.5, color=MUTED, fontweight="bold")
    for i, row in enumerate(district.head(5).itertuples(index=False)):
        y = 0.5 - i * 0.085
        table_panel.text(0.04, y, row.DISTRICT_LABEL, transform=table_panel.transAxes, fontsize=9, color=INK)
        table_panel.text(0.25, y, compact_number(row.total_requests), transform=table_panel.transAxes, fontsize=9, color=INK)
        table_panel.text(0.43, y, f"{row.avg_days:.1f}", transform=table_panel.transAxes, fontsize=9, color=INK)
        table_panel.text(0.6, y, f"{row.response_index:.2f}", transform=table_panel.transAxes, fontsize=9, color=RED if row.response_index > 1 else TEAL, fontweight="bold")
        table_panel.text(0.8, y, f"{row.open_share:.1%}", transform=table_panel.transAxes, fontsize=9, color=INK)

    fig.savefig(output_path, facecolor=BG)


def render_construction_dashboard(df: pd.DataFrame, output_path: Path) -> None:
    neighborhoods = (
        df.groupby("NEIGHBORHOOD", as_index=False)
        .agg(
            total_requests=("TOTAL_311_REQUESTS", "sum"),
            total_permits=("TOTAL_PERMITS", "sum"),
            active_permits=("ACTIVE_PERMIT_COUNT", "sum"),
            estimated_cost=("TOTAL_ESTIMATED_COST", "sum"),
            avg_days=("AVG_DAYS_TO_CLOSE", "mean"),
        )
    )
    permit_ratio = pd.to_numeric(
        neighborhoods["total_permits"] / neighborhoods["total_requests"].replace(0, pd.NA),
        errors="coerce",
    )
    neighborhoods["permit_request_ratio"] = permit_ratio.where(permit_ratio.notna(), 0.0).astype(float)
    cost_leaders = neighborhoods.sort_values("estimated_cost", ascending=False).head(8)
    ratio_leaders = neighborhoods[neighborhoods["total_requests"] >= 500].sort_values("permit_request_ratio", ascending=False).head(6)

    fig = base_figure(
        "Construction Pressure Dashboard",
        "Permit intensity, estimated value, and 311 demand side by side",
        "Construction x service demand",
    )
    add_kpi(fig, 0, "Permits", compact_number(neighborhoods["total_permits"].sum()), "Modeled permit volume", CORAL)
    add_kpi(fig, 1, "Estimated Cost", compact_number(neighborhoods["estimated_cost"].sum(), "$"), "Modeled permit value", GOLD)
    add_kpi(fig, 2, "Top Cost Area", short_label(cost_leaders.iloc[0]["NEIGHBORHOOD"], 16), compact_number(cost_leaders.iloc[0]["estimated_cost"], "$"), TEAL)
    add_kpi(fig, 3, "Highest Ratio", short_label(ratio_leaders.iloc[0]["NEIGHBORHOOD"], 16), f"{ratio_leaders.iloc[0]['permit_request_ratio']:.3f}", BLUE)

    scatter_panel = make_panel(fig, [0.045, 0.35, 0.52, 0.33], "Permits vs 311 Requests", "Bubble size is estimated construction value")
    ax_scatter = scatter_panel.inset_axes([0.08, 0.14, 0.86, 0.67])
    scatter_data = neighborhoods[neighborhoods["total_requests"] > 250]
    sizes = (scatter_data["estimated_cost"].clip(lower=0) / max(scatter_data["estimated_cost"].max(), 1)) * 540 + 25
    ax_scatter.scatter(scatter_data["total_requests"], scatter_data["total_permits"], s=sizes, c=scatter_data["avg_days"], cmap="plasma", alpha=0.72, edgecolors="#ffffff", linewidths=0.7)
    ax_scatter.set_xlabel("311 requests", color=MUTED, fontsize=8.5)
    ax_scatter.set_ylabel("Permits", color=MUTED, fontsize=8.5)
    ax_scatter.xaxis.set_major_formatter(FuncFormatter(k_formatter))
    clean_axis(ax_scatter)

    cost_panel = make_panel(fig, [0.595, 0.35, 0.36, 0.33], "Top Estimated Cost", "Neighborhoods sorted by modeled permit value")
    ax_cost = cost_panel.inset_axes([0.07, 0.12, 0.86, 0.68])
    cost_sorted = cost_leaders.sort_values("estimated_cost").copy()
    cost_sorted["display_name"] = cost_sorted["NEIGHBORHOOD"].apply(short_label)
    y_positions = range(len(cost_sorted))
    max_cost = cost_sorted["estimated_cost"].max()
    ax_cost.barh(y_positions, cost_sorted["estimated_cost"], color=GOLD, alpha=0.88)
    ax_cost.set_yticks([])
    ax_cost.set_xlim(-max_cost * 0.38, max_cost * 1.1)
    tick_step = 200_000_000
    tick_max = int(((max_cost * 1.05) // tick_step + 1) * tick_step)
    ax_cost.set_xticks(list(range(0, tick_max + 1, tick_step)))
    ax_cost.xaxis.set_major_formatter(FuncFormatter(k_formatter))
    for y, row in zip(y_positions, cost_sorted.itertuples(index=False)):
        ax_cost.text(-max_cost * 0.36, y, row.display_name, va="center", fontsize=8.2, color=INK)
    clean_axis(ax_cost)
    ax_cost.grid(True, axis="x", color=GRID, linewidth=0.8)
    ax_cost.grid(False, axis="y")

    ratio_panel = make_panel(fig, [0.045, 0.095, 0.91, 0.19], "Permit-to-Complaint Ratio Leaders", "Minimum 500 requests")
    for i, row in enumerate(ratio_leaders.itertuples(index=False)):
        x = 0.05 + (i % 3) * 0.31
        y = 0.56 - (i // 3) * 0.28
        ratio_panel.text(x, y, row.NEIGHBORHOOD, transform=ratio_panel.transAxes, fontsize=10, color=INK, fontweight="bold")
        ratio_panel.text(x, y - 0.12, f"{row.permit_request_ratio:.3f} permits/request  |  {compact_number(row.total_requests)} requests", transform=ratio_panel.transAxes, fontsize=8.5, color=MUTED)

    fig.savefig(output_path, facecolor=BG)


def render_neighborhood_dashboard(df: pd.DataFrame, output_path: Path) -> None:
    neighborhood = "Mission" if "Mission" in set(df["NEIGHBORHOOD"]) else df["NEIGHBORHOOD"].dropna().iloc[0]
    selected = df[df["NEIGHBORHOOD"] == neighborhood]
    monthly = (
        selected.groupby("MONTH_START_DATE", as_index=False)
        .agg(
            total_requests=("TOTAL_311_REQUESTS", "sum"),
            total_permits=("TOTAL_PERMITS", "sum"),
            open_requests=("OPEN_REQUEST_COUNT", "sum"),
            avg_days=("AVG_DAYS_TO_CLOSE", "mean"),
            estimated_cost=("TOTAL_ESTIMATED_COST", "sum"),
        )
        .assign(open_share=lambda data: data["open_requests"] / data["total_requests"].replace(0, pd.NA))
        .sort_values("MONTH_START_DATE")
    )
    total_requests = monthly["total_requests"].sum()
    total_permits = monthly["total_permits"].sum()
    total_cost = monthly["estimated_cost"].sum()
    avg_days = weighted_average(monthly["avg_days"], monthly["total_requests"])

    fig = base_figure(
        "Neighborhood Drilldown Dashboard",
        f"{neighborhood} monthly profile across 311 demand, permits, and response time",
        "Selected neighborhood lens",
    )
    add_kpi(fig, 0, "Neighborhood", neighborhood[:13], "Default drilldown selection", BLUE)
    add_kpi(fig, 1, "311 Requests", compact_number(total_requests), "Total modeled demand", TEAL)
    add_kpi(fig, 2, "Permits", compact_number(total_permits), "Permit activity", CORAL)
    add_kpi(fig, 3, "Estimated Cost", compact_number(total_cost, "$"), f"{avg_days:.1f} avg days", GOLD)

    trend_panel = make_panel(fig, [0.045, 0.37, 0.58, 0.31], f"{neighborhood} Monthly Profile", "Requests and permits sorted by month")
    ax_trend = trend_panel.inset_axes([0.07, 0.14, 0.87, 0.67])
    ax_trend.plot(monthly["MONTH_START_DATE"], monthly["total_requests"], color=BLUE, linewidth=2.5, label="311 requests")
    ax_trend.fill_between(monthly["MONTH_START_DATE"], monthly["total_requests"], color=BLUE, alpha=0.1)
    ax_permits = ax_trend.twinx()
    ax_permits.plot(monthly["MONTH_START_DATE"], monthly["total_permits"], color=CORAL, linewidth=2.2, label="Permits")
    ax_trend.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax_trend.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
    ax_trend.yaxis.set_major_formatter(FuncFormatter(k_formatter))
    ax_trend.set_ylabel("Requests", color=MUTED, fontsize=8.5)
    ax_permits.set_ylabel("Permits", color=MUTED, fontsize=8.5)
    clean_axis(ax_trend)
    for spine in ax_permits.spines.values():
        spine.set_visible(False)
    ax_permits.tick_params(colors=MUTED, labelsize=8.2)

    avg_panel = make_panel(fig, [0.655, 0.37, 0.3, 0.31], "Response Time Trend", "Average days to close")
    ax_avg = avg_panel.inset_axes([0.12, 0.14, 0.78, 0.67])
    ax_avg.bar(monthly["MONTH_START_DATE"], monthly["avg_days"], color=TEAL, alpha=0.86, width=20)
    ax_avg.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax_avg.xaxis.set_major_locator(mdates.MonthLocator(interval=5))
    ax_avg.set_ylabel("Avg days", color=MUTED, fontsize=8.5)
    clean_axis(ax_avg)

    table_panel = make_panel(fig, [0.045, 0.095, 0.91, 0.2], "Recent Monthly Detail", "Latest six months for the selected neighborhood")
    recent = monthly.tail(6).sort_values("MONTH_START_DATE", ascending=False)
    headers = ["Month", "Requests", "Permits", "Avg Days", "Open Share", "Est. Cost"]
    xs = [0.04, 0.2, 0.35, 0.5, 0.65, 0.8]
    for x, header in zip(xs, headers):
        table_panel.text(x, 0.65, header, transform=table_panel.transAxes, fontsize=8.5, color=MUTED, fontweight="bold")
    for i, row in enumerate(recent.itertuples(index=False)):
        y = 0.5 - i * 0.075
        values = [
            row.MONTH_START_DATE.strftime("%Y-%m"),
            compact_number(row.total_requests),
            compact_number(row.total_permits),
            f"{row.avg_days:.1f}",
            f"{row.open_share:.1%}",
            compact_number(row.estimated_cost, "$"),
        ]
        for x, value in zip(xs, values):
            table_panel.text(x, y, value, transform=table_panel.transAxes, fontsize=8.7, color=INK)

    fig.savefig(output_path, facecolor=BG)


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(CSV_PATH, parse_dates=["MONTH_START_DATE", "MONTH_END_DATE"])
    df["TOTAL_ESTIMATED_COST"] = df["TOTAL_ESTIMATED_COST"].fillna(0)
    df["TOTAL_PERMITS"] = df["TOTAL_PERMITS"].fillna(0)

    monthly = (
        df.groupby("MONTH_START_DATE", as_index=False)
        .agg(
            total_requests=("TOTAL_311_REQUESTS", "sum"),
            open_requests=("OPEN_REQUEST_COUNT", "sum"),
            total_permits=("TOTAL_PERMITS", "sum"),
            estimated_cost=("TOTAL_ESTIMATED_COST", "sum"),
            avg_days=("AVG_DAYS_TO_CLOSE", "mean"),
        )
        .sort_values("MONTH_START_DATE")
    )
    trend_monthly = monthly.copy()
    if len(trend_monthly) > 4:
        recent_median = trend_monthly["total_requests"].iloc[-4:-1].median()
        if trend_monthly["total_requests"].iloc[-1] < recent_median * 0.7:
            trend_monthly = trend_monthly.iloc[:-1]

    neighborhoods = (
        df.groupby("NEIGHBORHOOD", as_index=False)
        .agg(
            total_requests=("TOTAL_311_REQUESTS", "sum"),
            total_permits=("TOTAL_PERMITS", "sum"),
            estimated_cost=("TOTAL_ESTIMATED_COST", "sum"),
            avg_days=("AVG_DAYS_TO_CLOSE", "mean"),
        )
        .sort_values("total_requests", ascending=False)
    )

    district = (
        df[df["DISTRICT_LABEL"] != "Unassigned"]
        .groupby("DISTRICT_LABEL", as_index=False)
        .agg(
            total_requests=("TOTAL_311_REQUESTS", "sum"),
            open_requests=("OPEN_REQUEST_COUNT", "sum"),
            avg_days=("AVG_DAYS_TO_CLOSE", "mean"),
        )
        .assign(open_share=lambda data: data["open_requests"] / data["total_requests"])
        .sort_values("open_share", ascending=False)
        .head(7)
    )

    total_requests = df["TOTAL_311_REQUESTS"].sum()
    avg_days = df["AVG_DAYS_TO_CLOSE"].mean()
    total_permits = df["TOTAL_PERMITS"].sum()
    total_cost = df["TOTAL_ESTIMATED_COST"].sum()

    plt.rcParams["font.family"] = "DejaVu Sans"
    plt.rcParams["axes.titlelocation"] = "left"

    fig = plt.figure(figsize=(16, 9), dpi=160, facecolor=BG)

    fig.text(0.045, 0.94, "SF City Pulse", fontsize=31, fontweight="bold", color=INK)
    fig.text(
        0.045,
        0.905,
        "311 response equity, construction pressure, and neighborhood service demand",
        fontsize=13,
        color=MUTED,
    )
    fig.text(
        0.955,
        0.935,
        "Snowflake  |  dbt  |  Streamlit  |  Power BI",
        fontsize=11,
        color=MUTED,
        ha="right",
    )
    fig.text(
        0.955,
        0.905,
        "BI-ready monthly neighborhood mart",
        fontsize=9.5,
        color=TEAL,
        ha="right",
        fontweight="bold",
    )

    kpi_specs = [
        ("311 Requests", compact_number(total_requests), "Two-year service demand", BLUE),
        ("Avg. Days To Close", f"{avg_days:.1f}", "Citywide mean response time", TEAL),
        ("Permits", compact_number(total_permits), "Modeled construction activity", CORAL),
        ("Estimated Cost", compact_number(total_cost, "$"), "Permit value pressure", GOLD),
    ]

    for i, (label, value, note, color) in enumerate(kpi_specs):
        ax = fig.add_axes([0.045 + i * 0.235, 0.735, 0.205, 0.12])
        add_panel(ax)
        ax.axis("off")
        ax.text(0.07, 0.75, label.upper(), transform=ax.transAxes, fontsize=8.5, color=MUTED, fontweight="bold")
        ax.text(0.07, 0.37, value, transform=ax.transAxes, fontsize=25, color=INK, fontweight="bold")
        ax.text(0.07, 0.14, note, transform=ax.transAxes, fontsize=8.7, color=MUTED)
        ax.plot([0.72, 0.92], [0.78, 0.78], transform=ax.transAxes, color=color, linewidth=4.5, solid_capstyle="round")
        ax.plot([0.72, 0.92], [0.66, 0.66], transform=ax.transAxes, color=color, linewidth=4.5, alpha=0.35, solid_capstyle="round")

    trend_panel = make_panel(
        fig,
        [0.045, 0.405, 0.57, 0.27],
        "Monthly 311 Demand",
        "Complete months only, sorted chronologically",
    )
    ax_trend = trend_panel.inset_axes([0.055, 0.16, 0.9, 0.62])
    ax_trend.plot(trend_monthly["MONTH_START_DATE"], trend_monthly["total_requests"], color=BLUE, linewidth=2.7)
    ax_trend.fill_between(trend_monthly["MONTH_START_DATE"], trend_monthly["total_requests"], color=BLUE, alpha=0.12)
    clean_axis(ax_trend)
    ax_trend.yaxis.set_major_formatter(FuncFormatter(k_formatter))
    ax_trend.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax_trend.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
    ax_trend.tick_params(axis="x", labelsize=8.2)

    bar_panel = make_panel(
        fig,
        [0.645, 0.405, 0.31, 0.27],
        "Top Neighborhoods",
        "Ranked by total 311 request volume",
    )
    ax_bar = bar_panel.inset_axes([0.05, 0.13, 0.9, 0.66])
    top_neighborhoods = neighborhoods.head(7).copy()
    y_positions = range(len(top_neighborhoods))
    max_requests = top_neighborhoods["total_requests"].max()
    ax_bar.barh(y_positions, top_neighborhoods["total_requests"], color=TEAL, alpha=0.92, height=0.62)
    ax_bar.set_yticks([])
    ax_bar.set_xlim(-max_requests * 0.48, max_requests * 1.12)
    ax_bar.set_xticks(list(range(0, int(max_requests * 1.05) + 50_000, 50_000)))
    ax_bar.invert_yaxis()
    ax_bar.xaxis.set_major_formatter(FuncFormatter(k_formatter))
    ax_bar.tick_params(axis="x", labelsize=8.2)
    ax_bar.grid(True, axis="x", color=GRID, linewidth=0.8, alpha=0.8)
    ax_bar.grid(False, axis="y")
    for rank, row in enumerate(top_neighborhoods.itertuples(index=False), start=1):
        y = rank - 1
        ax_bar.text(-max_requests * 0.46, y, f"{rank}. {row.NEIGHBORHOOD}", va="center", fontsize=8.2, color=INK)
        ax_bar.text(row.total_requests + max_requests * 0.02, y, compact_number(row.total_requests), va="center", fontsize=8.0, color=MUTED)
    for spine in ax_bar.spines.values():
        spine.set_visible(False)

    scatter_panel = make_panel(
        fig,
        [0.045, 0.105, 0.42, 0.245],
        "Construction vs 311 Pressure",
        "Bubble size = estimated permit value",
    )
    ax_scatter = scatter_panel.inset_axes([0.085, 0.18, 0.86, 0.6])
    scatter_data = neighborhoods[neighborhoods["total_requests"] > 250].copy()
    sizes = (scatter_data["estimated_cost"].clip(lower=0) / max(scatter_data["estimated_cost"].max(), 1)) * 460 + 20
    ax_scatter.scatter(
        scatter_data["total_requests"],
        scatter_data["total_permits"],
        s=sizes,
        c=scatter_data["avg_days"],
        cmap="viridis",
        alpha=0.72,
        edgecolors="#ffffff",
        linewidths=0.7,
    )
    clean_axis(ax_scatter)
    ax_scatter.set_xlim(0, scatter_data["total_requests"].max() * 1.12)
    ax_scatter.set_ylim(0, scatter_data["total_permits"].max() * 1.18)
    ax_scatter.xaxis.set_major_formatter(FuncFormatter(k_formatter))
    ax_scatter.tick_params(axis="both", labelsize=8.2)
    ax_scatter.set_xlabel("311 requests", color=MUTED, labelpad=4, fontsize=8.5)
    ax_scatter.set_ylabel("Permits", color=MUTED, labelpad=4, fontsize=8.5)

    district_panel = make_panel(
        fig,
        [0.495, 0.105, 0.26, 0.245],
        "District Watchlist",
        "Sorted by open-request share",
    )
    ax_table = district_panel
    ax_table.text(0.06, 0.68, "District", transform=ax_table.transAxes, fontsize=8.3, color=MUTED, fontweight="bold")
    ax_table.text(0.58, 0.68, "Open", transform=ax_table.transAxes, fontsize=8.3, color=MUTED, fontweight="bold")
    ax_table.text(0.79, 0.68, "Days", transform=ax_table.transAxes, fontsize=8.3, color=MUTED, fontweight="bold")
    ax_table.plot([0.06, 0.94], [0.635, 0.635], transform=ax_table.transAxes, color=GRID, linewidth=1)

    for row_index, row in enumerate(district.itertuples(index=False), start=0):
        y = 0.56 - row_index * 0.068
        color = RED if row.open_share >= district["open_share"].quantile(0.75) else TEAL
        ax_table.text(0.06, y, row.DISTRICT_LABEL, transform=ax_table.transAxes, fontsize=8.8, color=INK)
        ax_table.text(0.58, y, f"{row.open_share:.1%}", transform=ax_table.transAxes, fontsize=8.8, color=color, fontweight="bold")
        ax_table.text(0.80, y, f"{row.avg_days:.1f}", transform=ax_table.transAxes, fontsize=8.8, color=INK)

    story_panel = make_panel(
        fig,
        [0.785, 0.105, 0.17, 0.245],
        "BI View",
        "Ready for Power BI or Tableau",
    )
    story_panel.text(0.08, 0.62, "Grain", transform=story_panel.transAxes, fontsize=8.2, color=MUTED, fontweight="bold")
    story_panel.text(0.08, 0.52, "Neighborhood x month", transform=story_panel.transAxes, fontsize=10, color=INK)
    story_panel.text(0.08, 0.38, "Model", transform=story_panel.transAxes, fontsize=8.2, color=MUTED, fontweight="bold")
    story_panel.text(0.08, 0.28, "BI_NEIGHBORHOOD_DASHBOARD", transform=story_panel.transAxes, fontsize=8.4, color=TEAL, fontweight="bold")
    story_panel.text(0.08, 0.14, "Includes city and district comparison fields", transform=story_panel.transAxes, fontsize=8.0, color=MUTED)

    fig.text(
        0.045,
        0.045,
        "Generated from SF_UDP_POC.MARTS.BI_NEIGHBORHOOD_DASHBOARD local extract",
        fontsize=8.2,
        color=MUTED,
    )

    fig.savefig(OUTPUT_PATH, facecolor=BG)
    render_equity_dashboard(df, EQUITY_OUTPUT_PATH)
    render_construction_dashboard(df, CONSTRUCTION_OUTPUT_PATH)
    render_neighborhood_dashboard(df, NEIGHBORHOOD_OUTPUT_PATH)
    for output_path in [OUTPUT_PATH, EQUITY_OUTPUT_PATH, CONSTRUCTION_OUTPUT_PATH, NEIGHBORHOOD_OUTPUT_PATH]:
        print(output_path)


if __name__ == "__main__":
    main()
