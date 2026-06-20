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


CSV_PATH = ROOT / "bi" / "sf_city_pulse_powerbi_extract.csv"
OUTPUT_PATH = ROOT / "docs" / "assets" / "sf-city-pulse-dashboard.png"

BG = "#f6f7f2"
PANEL = "#ffffff"
INK = "#111827"
MUTED = "#667085"
GRID = "#d7ddd0"
BLUE = "#2563eb"
TEAL = "#0f766e"
CORAL = "#f97316"
GOLD = "#ca8a04"
RED = "#dc2626"


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


def add_panel(ax, radius: float = 0.03) -> None:
    box = FancyBboxPatch(
        (0, 0),
        1,
        1,
        transform=ax.transAxes,
        boxstyle=f"round,pad=0.018,rounding_size={radius}",
        linewidth=1.0,
        edgecolor="#e1e6db",
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
        df.groupby("DISTRICT_LABEL", as_index=False)
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
    fig = plt.figure(figsize=(16, 10), dpi=150, facecolor=BG)
    gs = fig.add_gridspec(
        8,
        12,
        left=0.045,
        right=0.955,
        top=0.88,
        bottom=0.065,
        hspace=0.98,
        wspace=0.55,
    )

    fig.text(0.045, 0.95, "SF City Pulse", fontsize=30, fontweight="bold", color=INK)
    fig.text(
        0.045,
        0.915,
        "311 response equity x construction activity x neighborhood pressure",
        fontsize=13,
        color=MUTED,
    )
    fig.text(
        0.955,
        0.942,
        "Snowflake  |  dbt  |  Streamlit  |  Power BI",
        fontsize=11,
        color=MUTED,
        ha="right",
    )

    kpi_specs = [
        ("311 Requests", compact_number(total_requests), "Two-year service demand", BLUE),
        ("Avg. Days To Close", f"{avg_days:.1f}", "Citywide mean response time", TEAL),
        ("Permits", compact_number(total_permits), "Modeled construction activity", CORAL),
        ("Estimated Cost", compact_number(total_cost, "$"), "Permit value pressure", GOLD),
    ]

    for i, (label, value, note, color) in enumerate(kpi_specs):
        ax = fig.add_subplot(gs[0:2, i * 3 : (i + 1) * 3])
        add_panel(ax)
        ax.axis("off")
        ax.text(0.06, 0.75, label.upper(), transform=ax.transAxes, fontsize=9, color=MUTED, fontweight="bold")
        ax.text(0.06, 0.39, value, transform=ax.transAxes, fontsize=27, color=INK, fontweight="bold")
        ax.text(0.06, 0.16, note, transform=ax.transAxes, fontsize=9.5, color=MUTED)
        ax.plot([0.06, 0.34], [0.08, 0.08], transform=ax.transAxes, color=color, linewidth=4, solid_capstyle="round")

    ax_trend = fig.add_subplot(gs[2:5, 0:7])
    add_panel(ax_trend)
    clean_axis(ax_trend)
    ax_trend.plot(trend_monthly["MONTH_START_DATE"], trend_monthly["total_requests"], color=BLUE, linewidth=2.7)
    ax_trend.fill_between(trend_monthly["MONTH_START_DATE"], trend_monthly["total_requests"], color=BLUE, alpha=0.12)
    ax_trend.set_title("Monthly 311 Request Trend", loc="left", fontsize=14, fontweight="bold", color=INK, pad=14)
    ax_trend.set_ylabel("Requests", color=MUTED)
    ax_trend.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax_trend.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
    ax_trend.tick_params(axis="x", rotation=0)

    ax_bar = fig.add_subplot(gs[2:5, 7:12])
    add_panel(ax_bar)
    clean_axis(ax_bar)
    top_neighborhoods = neighborhoods.head(8).sort_values("total_requests")
    colors = [TEAL if i % 2 else CORAL for i in range(len(top_neighborhoods))]
    ax_bar.barh(top_neighborhoods["NEIGHBORHOOD"], top_neighborhoods["total_requests"], color=colors, alpha=0.9)
    ax_bar.set_title("Highest-Volume Neighborhoods", loc="left", fontsize=14, fontweight="bold", color=INK, pad=14)
    ax_bar.set_xlabel("Requests", color=MUTED)
    ax_bar.grid(True, axis="x", color=GRID, linewidth=0.8, alpha=0.8)
    ax_bar.grid(False, axis="y")

    ax_scatter = fig.add_subplot(gs[5:8, 0:7])
    add_panel(ax_scatter)
    clean_axis(ax_scatter)
    scatter_data = neighborhoods[neighborhoods["total_requests"] > 100].copy()
    sizes = (scatter_data["estimated_cost"].clip(lower=0) / max(scatter_data["estimated_cost"].max(), 1)) * 900 + 40
    ax_scatter.scatter(
        scatter_data["total_requests"],
        scatter_data["total_permits"],
        s=sizes,
        c=scatter_data["avg_days"],
        cmap="viridis",
        alpha=0.76,
        edgecolors="#ffffff",
        linewidths=0.7,
    )
    ax_scatter.set_title("Construction Pressure vs 311 Demand", loc="left", fontsize=14, fontweight="bold", color=INK, pad=18)
    ax_scatter.set_xlabel("311 requests", color=MUTED, labelpad=8)
    ax_scatter.set_ylabel("Permits", color=MUTED)

    ax_table = fig.add_subplot(gs[5:8, 7:12])
    add_panel(ax_table)
    ax_table.axis("off")
    ax_table.text(0.04, 0.9, "District Watchlist", transform=ax_table.transAxes, fontsize=14, fontweight="bold", color=INK)
    ax_table.text(0.04, 0.81, "Ranked by open-request share", transform=ax_table.transAxes, fontsize=9.5, color=MUTED)
    ax_table.text(0.04, 0.68, "District", transform=ax_table.transAxes, fontsize=9, color=MUTED, fontweight="bold")
    ax_table.text(0.56, 0.68, "Open Share", transform=ax_table.transAxes, fontsize=9, color=MUTED, fontweight="bold")
    ax_table.text(0.82, 0.68, "Avg Days", transform=ax_table.transAxes, fontsize=9, color=MUTED, fontweight="bold")
    ax_table.plot([0.04, 0.96], [0.64, 0.64], transform=ax_table.transAxes, color=GRID, linewidth=1)

    for row_index, row in enumerate(district.itertuples(index=False), start=0):
        y = 0.56 - row_index * 0.075
        color = RED if row.open_share >= district["open_share"].quantile(0.75) else TEAL
        ax_table.text(0.04, y, row.DISTRICT_LABEL, transform=ax_table.transAxes, fontsize=10, color=INK)
        ax_table.text(0.59, y, f"{row.open_share:.1%}", transform=ax_table.transAxes, fontsize=10, color=color, fontweight="bold")
        ax_table.text(0.84, y, f"{row.avg_days:.1f}", transform=ax_table.transAxes, fontsize=10, color=INK)

    fig.text(
        0.045,
        0.025,
        "Generated from SF_UDP_POC.MARTS.BI_NEIGHBORHOOD_DASHBOARD local extract",
        fontsize=8.5,
        color=MUTED,
    )

    fig.savefig(OUTPUT_PATH, facecolor=BG, bbox_inches="tight")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
