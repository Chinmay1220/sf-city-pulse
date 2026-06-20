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
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
