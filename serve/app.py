"""
Serve: MBTA Reliability & Ridership dashboard (Streamlit)

Reads:      gold.rail_incidents, gold.rail_ridership (cached for 15 minutes)
Deployed:   Cloud Run service `serve` (infra/cloud-run-services.tf), public at
            tylerclifton.com

Layout:
  1. Header + line filter
  2. Service status    — KPIs, incidents happening now, planned work coming up
  3. Incident patterns — when, where, why, and how long (since alert tracking began)
  4. Ridership         — per-line KPIs, monthly trend, incident impact, day of week
  5. Weather           — rain, snow, and temperature vs. typical ridership
  6. Footer            — sources, cadence, method notes

Time windows: every section covers the trailing 12 months, stated in its
subtitle. Two exceptions, also labeled: the monthly ridership trend shows 24
months (to compare each month with a year earlier) and weather uses all
available days (snowstorms are too rare for a single winter).

Counting unit is the incident (gold.rail_incidents): one real-world event the
MBTA may have posted as several alerts. An alert ends at its posted end time or
when it leaves the MBTA feed, whichever comes first (silver.mbta_alerts).

Ridership comparisons use "% vs typical": a day's gated entries relative to the
median for the same line, weekday, and month. That removes line size, the
weekday/weekend pattern, and seasonality, so what's left is the day's own effect.
"""

import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from google.cloud import bigquery
from pandas.tseries.holiday import USFederalHolidayCalendar

from helpers import TIMEZONE, esc, fmt_count, fmt_day, fmt_duration, fmt_pct, one_row_per_incident, strip_route_prefix

# ══════════════════════════════════════════════════════════════════════════════
# Design tokens
# ══════════════════════════════════════════════════════════════════════════════

# Surfaces and ink (dark theme; page background is set in .streamlit/config.toml)
CARD   = "#13161b"   # card surface
BORDER = "rgba(255,255,255,0.08)"
INK    = "#f0efec"   # primary text
INK_2  = "#b4b6bd"   # secondary text
MUTED  = "#80838c"   # axis labels, captions
GRID   = "#22252c"   # hairline gridlines
AXIS   = "#3a3e47"   # baselines

# Neutral accent for single-series charts — deliberately not a line color, so
# it never reads as "Blue Line" or "Green Line"
ACCENT = "#9085e9"

# One-hue sequential ramp (dark → lighter on the dark surface) for heatmaps;
# capped so white cell labels stay readable on the brightest cell
SEQUENTIAL = [[0.0, "#1c1a2e"], [1.0, "#7366d6"]]

FONT = "Inter, system-ui, -apple-system, 'Segoe UI', sans-serif"

# Official MBTA line colors — the identity of every line-level visual. Official
# Blue is low-contrast on the dark surface, so line-colored marks always carry
# a direct text label as well.
LINE_COLORS = {
    "Red Line":    "#DA291C",
    "Orange Line": "#ED8B00",
    "Blue Line":   "#003DA5",
    "Green Line":  "#00843D",
}
LINES = list(LINE_COLORS)

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Space between a mark and its value label (an em space), so labels never touch bars or dots
LABEL_GAP = "\u2003"

# Charts are read-only: no toolbar, zoom, or pan (they fight page scrolling on mobile)
CHART_CONFIG = {"displayModeBar": False, "scrollZoom": False, "doubleClick": False}

# ══════════════════════════════════════════════════════════════════════════════
# Page setup and global styles
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="MBTA Reliability & Ridership", page_icon="🚇", layout="wide")

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Typography: one sans everywhere (icons keep their own font) */
html, body, .stMarkdown, .stMarkdown *, .stCaption *, .st-key-line_filter button p,
[data-testid="stExpander"] summary p {{ font-family: {FONT} !important; }}

/* Page frame: centered column with generous gutters; hide Streamlit chrome */
.block-container {{ max-width: 1240px; padding: 3rem 2rem 4rem; }}
[data-testid="stHeader"] {{ display: none; }}

/* Header */
.hero h1 {{ font-size: 2.6rem; font-weight: 700; letter-spacing: -0.02em; line-height: 1.1;
            margin: 0 0 0.6rem; padding: 0; color: {INK}; }}
.hero p  {{ color: {INK_2}; font-size: 1.05rem; margin: 0 0 1rem; max-width: 54rem; }}
.status  {{ display: inline-flex; flex-wrap: wrap; gap: 0.35rem 1rem; color: {MUTED};
            font-size: 0.8rem; margin-bottom: 1.25rem; }}
.status .live::before {{ content: ""; display: inline-block; width: 7px; height: 7px;
            border-radius: 50%; background: #0ca30c; margin-right: 0.4rem; vertical-align: 1px; }}

/* Section headers */
.section {{ margin: 3.25rem 0 1rem; }}
.section h2 {{ font-size: 1.5rem; font-weight: 650; letter-spacing: -0.01em; margin: 0; padding: 0; color: {INK}; }}
.section p  {{ color: {INK_2}; font-size: 0.92rem; margin: 0.35rem 0 0; max-width: 52rem; }}

/* Cards: every st.container(key="card_...") */
div[class*="st-key-card_"] {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 14px;
            padding: 1.15rem 1.25rem 0.75rem; }}
.card-title {{ font-size: 1rem; font-weight: 600; color: {INK}; margin: 0; }}
.card-sub   {{ font-size: 0.82rem; color: {MUTED}; margin: 0.15rem 0 0.5rem; }}

/* KPI tiles */
.kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 0.75rem; }}
.kpi  {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 14px; padding: 1rem 1.1rem;
         position: relative; overflow: hidden; }}
.kpi .stripe {{ position: absolute; left: 0; top: 0; bottom: 0; width: 4px; }}
.kpi .label  {{ color: {MUTED}; font-size: 0.8rem; font-weight: 500; }}
.kpi .value  {{ color: {INK}; font-size: 2rem; font-weight: 650; letter-spacing: -0.02em;
               line-height: 1.2; margin-top: 0.2rem; }}
.kpi .sub    {{ color: {INK_2}; font-size: 0.8rem; margin-top: 0.15rem; }}
.delta-up   {{ color: #0ca30c; }}
.delta-down {{ color: #e66767; }}

/* Incident list items */
.inc {{ display: flex; gap: 0.85rem; padding: 0.8rem 0; border-top: 1px solid {BORDER}; }}
.inc:first-of-type {{ border-top: none; }}
.inc .bar  {{ width: 4px; border-radius: 2px; flex-shrink: 0; }}
.inc .top  {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem 0.55rem; }}
.inc .route {{ color: {INK}; font-weight: 600; font-size: 0.9rem; }}
.inc .badge {{ color: {INK_2}; font-size: 0.72rem; font-weight: 600; border: 1px solid {BORDER};
               border-radius: 999px; padding: 0.05rem 0.5rem; }}
.inc .cause {{ color: {MUTED}; font-size: 0.78rem; }}
.inc .text  {{ color: {INK_2}; font-size: 0.86rem; line-height: 1.45; margin-top: 0.3rem; }}
.inc .meta  {{ color: {MUTED}; font-size: 0.78rem; margin-top: 0.3rem; }}
.empty {{ color: {MUTED}; font-size: 0.9rem; padding: 0.5rem 0 1rem; }}

/* Line filter pills: a colored dot per line, in LINES order */
.st-key-line_filter button p::before {{ content: ""; display: inline-block; width: 8px; height: 8px;
            border-radius: 50%; margin-right: 0.45rem; vertical-align: 1px; background: var(--dot); }}
{"".join(f'.st-key-line_filter button:nth-of-type({i + 1}) {{ --dot: {color}; }}'
         for i, color in enumerate(LINE_COLORS.values()))}

/* Expanders blend into cards */
[data-testid="stExpander"] details {{ border: none; }}
[data-testid="stExpander"] summary {{ color: {INK_2}; font-size: 0.85rem; padding-left: 0; }}

/* Footer */
.footer {{ color: {MUTED}; font-size: 0.8rem; line-height: 1.6; border-top: 1px solid {BORDER};
           margin-top: 3.5rem; padding-top: 1.25rem; }}
.footer b {{ color: {INK_2}; font-weight: 600; }}

/* Phones: tighter gutters and type */
@media (max-width: 640px) {{
  .block-container {{ padding: 1.5rem 1rem 3rem; }}
  .hero h1 {{ font-size: 1.9rem; }}
  .section {{ margin-top: 2.5rem; }}
  .kpis {{ grid-template-columns: repeat(2, 1fr); }}
  .kpi .value {{ font-size: 1.5rem; }}
}}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# Layout helpers
# ══════════════════════════════════════════════════════════════════════════════

def section(title, subtitle=None):
    """Section heading with an optional one-line explanation."""
    sub = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(f'<div class="section"><h2>{title}</h2>{sub}</div>', unsafe_allow_html=True)


def card_title(title, subtitle=None):
    """Title (and optional subtitle) at the top of a card."""
    sub = f'<div class="card-sub">{subtitle}</div>' if subtitle else '<div class="card-sub"></div>'
    st.markdown(f'<div class="card-title">{title}</div>{sub}', unsafe_allow_html=True)


def kpi_tiles(tiles):
    """
    Row of KPI tiles. Each tile: dict(label, value, sub=None, color=None).
    `color` draws a left stripe (used for line-specific tiles).
    """
    cells = []
    for t in tiles:
        stripe = f'<div class="stripe" style="background:{t["color"]}"></div>' if t.get("color") else ""
        sub = f'<div class="sub">{t["sub"]}</div>' if t.get("sub") else ""
        cells.append(f'<div class="kpi">{stripe}<div class="label">{t["label"]}</div>'
                     f'<div class="value">{t["value"]}</div>{sub}</div>')
    st.markdown(f'<div class="kpis">{"".join(cells)}</div>', unsafe_allow_html=True)


def incident_items(df, when):
    """HTML list of incidents; `when(row)` returns the timing line."""
    items = []
    for _, row in df.iterrows():
        color = LINE_COLORS.get(row["line_name"], MUTED)
        items.append(
            f'<div class="inc"><div class="bar" style="background:{color}"></div><div>'
            f'<div class="top"><span class="route">{esc(row["route_name"])}</span>'
            f'<span class="badge">{esc(row["incident_effect"])}</span>'
            f'<span class="cause">{esc(row["incident_cause"])}</span></div>'
            f'<div class="text">{esc(strip_route_prefix(row["incident_header"]))}</div>'
            f'<div class="meta">{when(row)}</div></div></div>'
        )
    return "".join(items)


def incident_list(df, when, empty_text, limit=5):
    """First `limit` incidents inline; the rest behind a "Show more" expander."""
    if df.empty:
        st.markdown(f'<div class="empty">{empty_text}</div>', unsafe_allow_html=True)
        return
    st.markdown(incident_items(df.head(limit), when), unsafe_allow_html=True)
    if len(df) > limit:
        with st.expander(f"Show {len(df) - limit} more"):
            st.markdown(incident_items(df.iloc[limit:], when), unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# Chart helpers — one look for every chart
# ══════════════════════════════════════════════════════════════════════════════

def style(fig, height=300, legend=False):
    """Apply the shared chart style: transparent surface, hairline grid, muted axes."""
    # automargin grows the margin to fit long tick labels ("Medical Emergency")
    # instead of clipping them; standoff keeps labels off the axis line
    axis = dict(gridcolor=GRID, linecolor=AXIS, zeroline=False, fixedrange=True, automargin=True,
                tickfont=dict(color=MUTED, size=11), title=None, ticks="")
    fig.update_layout(
        height=height,
        margin=dict(l=4, r=12, t=8, b=4),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color=INK_2, size=12),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(color=INK_2, size=11),
                    bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="#1c2027", bordercolor=BORDER, font=dict(family=FONT, color=INK, size=12)),
        bargap=0.35,
        xaxis=dict(axis, ticklabelstandoff=6),
        yaxis=dict(axis, ticklabelstandoff=10),
    )
    return fig


def count_axis(fig, top, axis="y"):
    """Label a count axis like the KPI tiles (126K, 3.2M) with ~4 round ticks from 0 to `top`."""
    raw = max(top, 1) / 4
    magnitude = 10 ** np.floor(np.log10(raw))
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)
    ticks = np.arange(0, top + step, step)
    getattr(fig, f"update_{axis}axes")(tickvals=ticks, ticktext=[fmt_count(t) for t in ticks],
                                       range=[0, ticks[-1] * 1.04])


def show(fig):
    st.plotly_chart(fig, config=CHART_CONFIG, width="stretch")


def ranked_bars(labels, values, text, hover, colors=ACCENT, height=None):
    """Horizontal bars, largest on top, value label at each bar's tip."""
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker=dict(color=colors, cornerradius=4),
        text=[LABEL_GAP + t for t in text], textposition="outside",
        textfont=dict(color=INK_2, size=11), cliponaxis=False,
        hovertext=hover, hoverinfo="text",
    ))
    style(fig, height=height or max(180, 34 * len(labels) + 30))
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)", tickfont=dict(color=INK_2, size=12))
    # Value labels render into a fixed right margin (not a share of the axis),
    # so the longest label fits at every screen width
    fig.update_layout(margin=dict(l=4, r=84, t=8, b=4))
    fig.update_xaxes(visible=False, range=[0, max(values) * 1.02 if len(values) else 1])
    return fig


def band_bars(df, height=260):
    """
    Weather-band bars: each band vs the normal-conditions band (drawn at zero),
    signed label on each bar. Expects columns band, pct, days.
    """
    fig = go.Figure(go.Bar(
        x=df["band"].astype(str), y=df["pct"],
        marker=dict(color=ACCENT, cornerradius=4),
        # The baseline band is zero by definition; label it as such
        text=["baseline" if abs(v) < 1e-9 else fmt_pct(v) for v in df["pct"]], textposition="outside",
        cliponaxis=False, textfont=dict(color=INK_2, size=11),
        hovertext=[f"{band}<br>{fmt_pct(pct)} vs normal days · {days} days"
                   for band, pct, days in zip(df["band"], df["pct"], df["days"], strict=True)],
        hoverinfo="text",
    ))
    style(fig, height=height)
    span = max(abs(df["pct"]).max(), 2) * 1.35
    fig.update_yaxes(range=[-span, span], ticksuffix="%", zeroline=True, zerolinecolor=AXIS, zerolinewidth=1)
    fig.update_xaxes(tickfont=dict(color=INK_2, size=11))
    return fig

# ══════════════════════════════════════════════════════════════════════════════
# Data
# ══════════════════════════════════════════════════════════════════════════════

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "mbta-reliability-analytics")
# Dataset to read; point at dev_gold to preview a local dbt build
GOLD_DATASET = os.getenv("GOLD_DATASET", "gold")


@st.cache_resource
def get_client():
    return bigquery.Client(project=PROJECT_ID)


# Cache 15 minutes: gold rebuilds hourly, so the page is at most ~75 minutes behind
@st.cache_data(ttl=900, show_spinner=False)
def load_incidents():
    df = get_client().query(f"""
        SELECT
            incident_id, route_id, route_name, line_name,
            incident_cause, incident_effect, incident_header,
            incident_start_at, incident_end_at, incident_duration_minutes,
            alert_count, is_in_feed, ingested_at
        FROM `{PROJECT_ID}.{GOLD_DATASET}.rail_incidents`
    """).to_dataframe()
    for col in ["incident_start_at", "incident_end_at", "ingested_at"]:
        df[col] = pd.to_datetime(df[col], utc=True)
    return df


@st.cache_data(ttl=900, show_spinner=False)
def load_ridership():
    df = get_client().query(f"""
        SELECT
            service_date, line_name, gated_entries, active_incident_count,
            most_severe_effect, avg_temperature_f, precipitation_in, snowfall_in
        FROM `{PROJECT_ID}.{GOLD_DATASET}.rail_ridership`
    """).to_dataframe()
    df["service_date"] = pd.to_datetime(df["service_date"])

    # "% vs typical": entries relative to the median for the same line, weekday,
    # and month — strips out line size, weekday pattern, and seasonality
    df["weekday"] = df["service_date"].dt.dayofweek
    df["month"] = df["service_date"].dt.to_period("M")
    typical = df.groupby(["line_name", "weekday", "month"])["gated_entries"].transform("median")
    df["pct_vs_typical"] = (df["gated_entries"] / typical - 1) * 100

    # Federal holidays are not typical for their weekday; flag them so "% vs typical" comparisons skip them
    holidays = USFederalHolidayCalendar().holidays(df["service_date"].min(), df["service_date"].max())
    df["is_holiday"] = df["service_date"].isin(holidays)
    return df


incidents_all = load_incidents()
ridership_all = load_ridership()

now = pd.Timestamp.now(tz="UTC")

if incidents_all.empty and ridership_all.empty:
    st.warning("No data available yet.")
    st.stop()

# Alert tracking began with the first ingest run; incident history starts there
tracking_start = incidents_all["ingested_at"].min()

# Incident history only counts from when coverage became continuous. The
# subway never goes two weeks without an incident, so a gap that long means
# alerts weren't being captured (the pre-October pipeline missed June 8 – July 1,
# 2026). Coverage starts at the first incident after the last such gap, measured
# from the start of tracking and over incidents that have already begun (gaps
# between future planned work don't count). Before it, an empty day would read
# as "no disruption" when it's really no data.
_now = pd.Timestamp.now(tz="UTC")
_starts = incidents_all.loc[incidents_all["incident_start_at"].between(tracking_start, _now), "incident_start_at"]
_starts = pd.concat([pd.Series([tracking_start]), _starts]).sort_values().reset_index(drop=True)
_after_gap = _starts[_starts.diff() > pd.Timedelta(days=14)]
coverage_start = _after_gap.iloc[-1] if len(_after_gap) else tracking_start

# ══════════════════════════════════════════════════════════════════════════════
# 1. Header + line filter
# ══════════════════════════════════════════════════════════════════════════════

alerts_updated = incidents_all["ingested_at"].max()
ridership_through = ridership_all["service_date"].max()

st.markdown(f"""
<div class="hero">
  <h1>MBTA Reliability &amp; Ridership</h1>
  <p>Service incidents, ridership, and weather across Boston's Red, Orange, Blue, and Green Lines.</p>
  <div class="status">
    <span class="live">Alerts updated {alerts_updated.tz_convert(TIMEZONE).strftime("%b %-d, %-I:%M %p ET")}</span>
    <span>Ridership through {ridership_through.strftime("%b %-d, %Y")}</span>
  </div>
</div>
""", unsafe_allow_html=True)

selected_lines = st.pills(
    "Lines", LINES, selection_mode="multi", default=LINES,
    key="line_filter", label_visibility="collapsed",
) or LINES  # Nothing selected → show everything rather than an empty page

incidents = incidents_all[incidents_all["line_name"].isin(selected_lines)]
ridership = ridership_all[ridership_all["line_name"].isin(selected_lines)]

# ══════════════════════════════════════════════════════════════════════════════
# 2. Service status
# ══════════════════════════════════════════════════════════════════════════════

section("Service status", "Incidents on the selected lines right now, and planned work ahead.")

active = one_row_per_incident(incidents[
    (incidents["incident_start_at"] <= now)
    & (incidents["incident_end_at"].isna() | (incidents["incident_end_at"] >= now))
]).sort_values("incident_start_at", ascending=False)

upcoming = one_row_per_incident(incidents[incidents["incident_start_at"] > now]).sort_values("incident_start_at")
upcoming_30d = upcoming[upcoming["incident_start_at"] <= now + pd.Timedelta(days=30)]

# Incidents that have started. `started` keeps gold's incident × route rows (for
# per-line counts); `started_events` has one row per incident, so an event on
# four Green Line branches counts once everywhere incidents are counted.
started = incidents[incidents["incident_start_at"] <= now]
started_events = one_row_per_incident(started)
last_30 = started_events[started_events["incident_start_at"] > now - pd.Timedelta(days=30)]
prior_30 = started_events[(started_events["incident_start_at"] <= now - pd.Timedelta(days=30))
                          & (started_events["incident_start_at"] > now - pd.Timedelta(days=60))]

# Change vs the previous 30 days; fewer incidents is good (green)
if len(prior_30):
    change = (len(last_30) / len(prior_30) - 1) * 100
    css = "delta-up" if change <= 0 else "delta-down"
    arrow = "▼" if change <= 0 else "▲"
    trend = f'<span class="{css}">{arrow} {abs(change):.0f}%</span> vs prior 30 days'
else:
    trend = "first 30 days of tracking"

active_lines = active["line_name"].nunique()
kpi_tiles([
    dict(label="Active now", value=f"{len(active)}",
         sub=f"on {active_lines} line{'s' if active_lines != 1 else ''}" if len(active) else "all clear"),
    dict(label="Planned work · next 30 days", value=f"{len(upcoming_30d)}",
         sub=(f"next starts {fmt_day(upcoming_30d['incident_start_at'].iloc[0])}"
              if len(upcoming_30d) else "none scheduled")),
    dict(label="Incidents · last 30 days", value=f"{len(last_30)}", sub=trend),
    dict(label="Median duration · last 30 days", value=fmt_duration(last_30["incident_duration_minutes"].median()),
         sub="first alert to all-clear"),
])

st.write("")
now_col, next_col = st.columns(2, gap="medium")

with now_col:
    with st.container(key="card_active"):
        card_title("Happening now", f"{len(active)} active incident{'s' if len(active) != 1 else ''}")
        incident_list(
            active,
            lambda r: (f"Since {fmt_day(r['incident_start_at'])} · "
                       + (f"until {fmt_day(r['incident_end_at'])}" if pd.notna(r["incident_end_at"])
                          else "no end time posted")
                       + f" · {fmt_duration(r['incident_duration_minutes'])}"
                       + (" so far" if pd.isna(r["incident_end_at"]) else "")),
            "No active incidents on the selected lines.",
        )

with next_col:
    with st.container(key="card_upcoming"):
        card_title("Coming up", f"{len(upcoming)} planned by the MBTA")
        incident_list(
            upcoming,
            lambda r: (f"Starts {fmt_day(r['incident_start_at'])}"
                       + (f" · until {fmt_day(r['incident_end_at'])}" if pd.notna(r["incident_end_at"]) else "")
                       + f" · {fmt_duration(r['incident_duration_minutes'])}"),
            "No planned work announced.",
        )

# ══════════════════════════════════════════════════════════════════════════════
# 3. Incident patterns
# ══════════════════════════════════════════════════════════════════════════════

# Trailing 12 months — or since alert tracking began, while that's more recent
year_ago = now - pd.DateOffset(months=12)
window_start = max(coverage_start, year_ago)
history = started[started["incident_start_at"] >= window_start]                     # incident × route
history_events = started_events[started_events["incident_start_at"] >= window_start]  # one per incident
window_label = ("Trailing 12 months" if window_start == year_ago
                else f"Since continuous alert tracking began on {fmt_day(coverage_start)}, {coverage_start.year}"
                     " (less than 12 months ago)")

section(
    "Incident patterns",
    f"{window_label}. Re-posted alerts for the same event count once.",
)

if history.empty:
    st.markdown('<div class="empty">No incidents recorded yet.</div>', unsafe_allow_html=True)
else:
    # ── When: incidents per week ──────────────────────────────────────────────
    week_col, line_col = st.columns([3, 2], gap="medium")
    with week_col:
        with st.container(key="card_weekly"):
            card_title("Incidents per week", "By the week the incident started · lighter bars: partial weeks")
            weeks = (history_events["incident_start_at"].dt.tz_convert(TIMEZONE).dt.tz_localize(None)
                     .dt.to_period("W-SUN").dt.start_time)
            weekly = weeks.value_counts().sort_index()
            weekly = weekly.reindex(pd.date_range(weekly.index.min(), weekly.index.max(), freq="7D"), fill_value=0)
            # Partial weeks — the one coverage starts in (unless it starts on a
            # Monday) and the current one — are drawn lighter
            this_week = pd.Timestamp.now(tz=TIMEZONE).tz_localize(None).to_period("W-SUN").start_time
            first_day = window_start.tz_convert(TIMEZONE).tz_localize(None).normalize()
            first_week = first_day.to_period("W-SUN").start_time if first_day.dayofweek else None
            partial = {this_week, first_week}
            opacity = [0.45 if w in partial else 1.0 for w in weekly.index]
            week_note = {this_week: " (so far)", first_week: " (partial)"}
            fig = go.Figure(go.Bar(
                x=weekly.index, y=weekly.values,
                marker=dict(color=ACCENT, cornerradius=4, opacity=opacity),
                hovertext=[f"Week of {w:%b %-d}{week_note.get(w, '')}<br>{n} incidents"
                           for w, n in weekly.items()],
                hoverinfo="text",
            ))
            style(fig, height=260)
            fig.update_xaxes(tickformat="%b %-d", gridcolor="rgba(0,0,0,0)")
            show(fig)

    # ── Where: incidents by line ──────────────────────────────────────────────
    with line_col:
        with st.container(key="card_by_line"):
            card_title("Incidents by line", "On any of the line's routes")
            by_line = history.groupby("line_name")["incident_id"].nunique().reindex(selected_lines).fillna(0)
            line_share = by_line / max(by_line.sum(), 1) * 100
            show(ranked_bars(
                labels=list(by_line.index), values=list(by_line.values),
                text=[f"{v:.0f}  ·  {s:.0f}%" for v, s in zip(by_line.values, line_share.values, strict=True)],
                hover=[f"{line}: {v:.0f} incidents ({s:.0f}%)"
                       for line, v, s in zip(by_line.index, by_line.values, line_share.values, strict=True)],
                colors=[LINE_COLORS[line] for line in by_line.index], height=260,
            ))

    # ── Why: causes and effects ───────────────────────────────────────────────
    cause_col, effect_col = st.columns(2, gap="medium")
    cause_counts = history_events["incident_cause"].value_counts()
    top_causes = cause_counts.head(7)
    if len(cause_counts) > 7:
        top_causes["Other"] = cause_counts.iloc[7:].sum()

    with cause_col:
        with st.container(key="card_causes"):
            card_title("Incidents by cause", "Top causes; the rest grouped as Other")
            share = top_causes / top_causes.sum() * 100
            show(ranked_bars(
                labels=list(top_causes.index), values=list(top_causes.values),
                text=[f"{n}  ·  {s:.0f}%" for n, s in zip(top_causes.values, share.values, strict=True)],
                hover=[f"{cause}: {n} incidents ({s:.0f}%)"
                       for cause, n, s in zip(top_causes.index, top_causes.values, share.values, strict=True)],
            ))

    with effect_col:
        with st.container(key="card_effects"):
            card_title("Incidents by effect", "How service was affected")
            effects = history_events["incident_effect"].value_counts()
            share = effects / effects.sum() * 100
            show(ranked_bars(
                labels=list(effects.index), values=list(effects.values),
                text=[f"{n}  ·  {s:.0f}%" for n, s in zip(effects.values, share.values, strict=True)],
                hover=[f"{effect}: {n} incidents ({s:.0f}%)"
                       for effect, n, s in zip(effects.index, effects.values, share.values, strict=True)],
                height=max(180, 34 * len(top_causes) + 30),  # match the causes card
            ))

    # ── How long, and where each cause hits ───────────────────────────────────
    dur_col, mix_col = st.columns(2, gap="medium")
    named_causes = [c for c in top_causes.index if c != "Other"]

    with dur_col:
        with st.container(key="card_duration"):
            card_title("Duration by cause", "Median, from first alert to all-clear")
            dur = (history_events[history_events["incident_cause"].isin(named_causes)]
                   .groupby("incident_cause")["incident_duration_minutes"].median()
                   .reindex(named_causes))
            fig = go.Figure(go.Scatter(
                x=dur.values, y=dur.index, mode="markers+text",
                marker=dict(color=ACCENT, size=11, line=dict(color=CARD, width=2)),
                text=[LABEL_GAP + fmt_duration(v) for v in dur.values], textposition="middle right",
                textfont=dict(color=INK_2, size=11), cliponaxis=False,
                hovertext=[f"{c}: median {fmt_duration(v)}" for c, v in dur.items()], hoverinfo="text",
            ))
            style(fig, height=max(180, 34 * len(named_causes) + 40))
            if dur.max() < 1440:
                # Everything under a day: linear hours read more naturally
                hours = int(np.ceil(dur.max() / 60)) + 1
                fig.update_xaxes(range=[0, hours * 60 * 1.15], tickvals=[h * 60 for h in range(0, hours + 1)],
                                 ticktext=[f"{h} hr" for h in range(0, hours + 1)])
            else:
                # Mixed hours and days: log scale keeps short causes readable
                fig.update_xaxes(type="log", tickvals=[60, 360, 1440, 10080, 43200],
                                 ticktext=["1 hr", "6 hr", "1 day", "1 wk", "1 mo"],
                                 range=[np.log10(20), np.log10(200000)])
            fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)", tickfont=dict(color=INK_2, size=12))
            show(fig)

    with mix_col:
        with st.container(key="card_mix"):
            card_title("Cause mix by line", "Share of each line's incidents, top causes")
            mix = (history[history["incident_cause"].isin(named_causes)]
                   .groupby(["incident_cause", "line_name"])["incident_id"].nunique().unstack(fill_value=0)
                   .reindex(index=named_causes, columns=selected_lines, fill_value=0))
            mix_pct = mix / history.groupby("line_name")["incident_id"].nunique().reindex(selected_lines) * 100
            fig = go.Figure(go.Heatmap(
                z=mix_pct.values, x=list(mix_pct.columns), y=mix_pct.index,
                colorscale=SEQUENTIAL, showscale=False, xgap=3, ygap=3,
                text=[[f"{v:.0f}%" for v in row] for row in mix_pct.values], texttemplate="%{text}",
                textfont=dict(size=11, color=INK),
                hovertemplate="%{y} · %{x}<br>%{text} of incidents<extra></extra>",
            ))
            style(fig, height=max(180, 34 * len(named_causes) + 40))
            fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)", tickfont=dict(color=INK_2, size=12))
            fig.update_xaxes(side="top", gridcolor="rgba(0,0,0,0)", tickfont=dict(color=INK_2, size=12),
                             tickvals=list(mix_pct.columns),
                             ticktext=[line.replace(" ", "<br>") for line in mix_pct.columns])
            show(fig)

# ══════════════════════════════════════════════════════════════════════════════
# 4. Ridership
# ══════════════════════════════════════════════════════════════════════════════

if ridership.empty:
    section("Ridership")
    st.markdown('<div class="empty">No ridership data available yet.</div>', unsafe_allow_html=True)
    st.stop()

# Complete months only (the MBTA publishes whole months, but guard the edges)
month_days = ridership.groupby(["line_name", "month"])["service_date"].nunique().rename("days").reset_index()
month_days = month_days[month_days["days"] == month_days["month"].dt.days_in_month]
full_months = ridership.merge(month_days[["line_name", "month"]], on=["line_name", "month"])
latest_month = full_months["month"].max()
year_ago_label = (latest_month - 12).strftime("%b %Y")
latest_month_name = latest_month.strftime("%B")  # Periods don't take f-string date formats

# Ridership's window ends at the latest published day, not today (the MBTA
# publishes one to two months behind)
ridership_year_start = ridership_through - pd.DateOffset(months=12) + pd.Timedelta(days=1)

section(
    "Ridership",
    f"Trailing 12 months, through {ridership_through:%b %Y} — the latest the MBTA has published (it runs "
    "one to two months behind). All figures are average entries per day, weekends included; the tiles "
    f"compare {latest_month_name} with a year earlier.",
)

# Every day except federal holidays — for the "% vs typical" comparisons, where
# a holiday isn't a typical day for its weekday. Each day is compared with its
# own weekday (see load_ridership), so weekends are included like-for-like.
ordinary_days = ridership[~ridership["is_holiday"]]

# ── Per-line KPIs: average entries per day in the latest month, year over year ──
tiles = []
for line in selected_lines:
    days = ridership[ridership["line_name"] == line]
    current = days[days["month"] == latest_month]["gated_entries"].mean()
    year_ago = days[days["month"] == latest_month - 12]["gated_entries"].mean()
    if pd.notna(year_ago) and year_ago:
        change = (current / year_ago - 1) * 100
        sub = (f'<span class="{"delta-up" if change >= 0 else "delta-down"}">{"▲" if change >= 0 else "▼"} '
               f'{abs(change):.1f}%</span> vs {year_ago_label}')
    else:
        sub = "no prior-year data"
    tiles.append(dict(label=line,
                      value=fmt_count(current) if pd.notna(current) else "—", sub=sub, color=LINE_COLORS[line]))
kpi_tiles(tiles)
st.write("")

# ── Monthly trend ─────────────────────────────────────────────────────────────
with st.container(key="card_monthly"):
    card_title("Monthly ridership", "Average entries per day · last 24 months, to compare with a year earlier")
    # Average per day, not monthly totals: months run 28–31 days, which would
    # move totals with no change in ridership. The month's total is in the hover.
    trend_months = full_months[full_months["month"] > latest_month - 24]
    monthly = (trend_months.groupby(["month", "line_name"])["gated_entries"]
               .agg(daily_avg="mean", total="sum")
               .reset_index())
    monthly["month_start"] = monthly["month"].dt.start_time
    fig = go.Figure()
    for line in selected_lines:
        m = monthly[monthly["line_name"] == line].sort_values("month_start")
        if m.empty:
            continue
        fig.add_trace(go.Scatter(
            x=m["month_start"], y=m["daily_avg"], name=line, mode="lines",
            line=dict(color=LINE_COLORS[line], width=2.5),
            customdata=m["total"],
            hovertemplate=(f"{line} · %{{x|%b %Y}}<br>%{{y:,.0f}} per day"
                           "<br>%{customdata:,.0f} entries that month<extra></extra>"),
        ))
        # Direct label + end dot at the latest month (identity is never color alone)
        last = m.iloc[-1]
        fig.add_trace(go.Scatter(
            x=[last["month_start"]], y=[last["daily_avg"]], mode="markers+text",
            marker=dict(color=LINE_COLORS[line], size=9, line=dict(color=CARD, width=2)),
            text=[f"{LABEL_GAP}{line} · {fmt_count(last['daily_avg'])}"],
            textposition="middle right", textfont=dict(color=INK_2, size=11),
            showlegend=False, hoverinfo="skip", cliponaxis=False,
        ))
    style(fig, height=340)
    fig.update_layout(margin=dict(l=4, r=128, t=8, b=4))
    # Yearly ticks stay legible at phone width (the end labels take the right margin)
    fig.update_xaxes(tickformat="%b %Y", gridcolor="rgba(0,0,0,0)", dtick="M12", tick0="2025-01-01", tickangle=0)
    count_axis(fig, monthly["daily_avg"].max())
    show(fig)

impact_col, dow_col = st.columns(2, gap="medium")

# ── Ridership by alert effect (replaces the old dual-axis chart) ─────────────
with impact_col:
    with st.container(key="card_impact"):
        tracking_day = coverage_start.tz_convert(TIMEZONE).tz_localize(None).normalize()
        impact_start = max(tracking_day, ridership_year_start)
        card_title("Ridership by alert effect",
                   "Compared with calm days"
                   + ("" if impact_start == ridership_year_start
                      else f" · since continuous alert tracking began {fmt_day(coverage_start)}"))
        tracked = ordinary_days[ordinary_days["service_date"] >= impact_start]
        if tracked.empty:
            st.markdown('<div class="empty">Not enough overlapping data yet.</div>', unsafe_allow_html=True)
        else:
            # Each line-day counts under its most severe effect (gold.rail_ridership);
            # pooled across the selected lines, since one line alone has too few
            # shuttle or suspension days to trust. Calm days are the baseline.
            effects = ["Delay", "Suspension", "Shuttle"]
            by_effect = (tracked.assign(effect=tracked["most_severe_effect"].fillna("Calm"))
                         .groupby("effect")
                         .agg(pct=("pct_vs_typical", "mean"), days=("service_date", "size")))
            rows = []
            if "Calm" in by_effect.index:
                calm = by_effect.loc["Calm"]
                for effect in effects:
                    if effect in by_effect.index:
                        hit = by_effect.loc[effect]
                        diff = ((1 + hit["pct"] / 100) / (1 + calm["pct"] / 100) - 1) * 100
                        rows.append((effect, diff, int(hit["days"])))
            if not rows:
                st.markdown('<div class="empty">Not enough calm days to compare yet.</div>', unsafe_allow_html=True)
            else:
                fig = go.Figure(go.Bar(
                    x=[diff for _, diff, _ in rows], y=[effect for effect, *_ in rows], orientation="h",
                    marker=dict(color=ACCENT, cornerradius=4),
                    text=[LABEL_GAP + fmt_pct(diff) + LABEL_GAP for _, diff, _ in rows], textposition="outside",
                    textfont=dict(color=INK_2, size=11), cliponaxis=False,
                    hovertext=[f"{effect}: {fmt_pct(diff)} vs calm days<br>{days} line-days"
                               f" · {int(calm['days'])} calm line-days"
                               for effect, diff, days in rows],
                    hoverinfo="text",
                ))
                style(fig, height=230)
                # Room past the longest bar for its label, at phone width too
                span = max([abs(diff) for _, diff, _ in rows] + [2]) * 1.8
                fig.update_xaxes(range=[-span, span], ticksuffix="%", zeroline=True, zerolinecolor=AXIS,
                                 zerolinewidth=1)
                fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)",
                                 tickfont=dict(color=INK_2, size=12))
                show(fig)
                st.caption("0% = calm days. Each day counts under its most severe alert: shuttle buses, then a "
                           "suspension, then a delay. Delays rarely last long enough to move a day's total; "
                           "shuttle riders skip the fare gates entirely. Holidays excluded.")

# ── Day of week ───────────────────────────────────────────────────────────────
with dow_col:
    with st.container(key="card_dow"):
        card_title("Ridership by day of week", "Average entries per day")
        recent = ridership[ridership["service_date"] >= ridership_year_start]
        dow = recent.groupby(["weekday", "line_name"])["gated_entries"].mean().reset_index()
        fig = go.Figure()
        for line in selected_lines:
            d = dow[dow["line_name"] == line].sort_values("weekday")
            fig.add_trace(go.Bar(
                x=[WEEKDAYS[i][:3] for i in d["weekday"]], y=d["gated_entries"], name=line,
                marker=dict(color=LINE_COLORS[line], cornerradius=3),
                hovertemplate=f"{line}<br>%{{x}}: %{{y:,.0f}} per day<extra></extra>",
            ))
        style(fig, height=280, legend=True)
        fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.12)
        count_axis(fig, dow["gated_entries"].max())
        fig.update_xaxes(gridcolor="rgba(0,0,0,0)", tickfont=dict(color=INK_2, size=12))
        show(fig)

# ══════════════════════════════════════════════════════════════════════════════
# 5. Weather
# ══════════════════════════════════════════════════════════════════════════════

section(
    "Weather",
    f"Every day since {ridership_all['service_date'].min():%b %Y} — snowstorms and downpours are too rare "
    "to judge from one year. Each day is measured against typical for its line, weekday, and month, then "
    "compared with normal-weather days. Holidays are left out of this comparison only.",
)

wx = ordinary_days.dropna(subset=["avg_temperature_f"])


def band_summary(df, column, bins, labels, baseline):
    """
    Average % vs typical per band of `column`, re-expressed relative to the
    `baseline` band (normal conditions), so the chart reads "heavy rain days
    run 5.7 points below dry days". Also returns the day count per band.
    """
    banded = df.assign(band=pd.cut(df[column], bins=bins, labels=labels))
    summary = (banded.groupby("band", observed=False)
               .agg(pct=("pct_vs_typical", "mean"), days=("service_date", "nunique"))
               .reset_index().dropna(subset=["pct"]))
    reference = summary.loc[summary["band"] == baseline, "pct"]
    summary["pct"] -= reference.iloc[0] if len(reference) else 0
    return summary


rain_col, snow_col, temp_col = st.columns(3, gap="medium")

with rain_col:
    with st.container(key="card_rain"):
        card_title("Rain", "By daily rainfall · snow days are in the Snow chart")
        rain = band_summary(wx[wx["snowfall_in"].fillna(0) == 0], "precipitation_in",
                            [-0.01, 0, 0.1, 0.5, 100], ["Dry", "Light", "Moderate", "Heavy"], baseline="Dry")
        show(band_bars(rain))
        st.caption("Light ≤ 0.1″ · Moderate 0.1–0.5″ · Heavy > 0.5″")

with snow_col:
    with st.container(key="card_snow"):
        card_title("Snow", "By daily snowfall · December–March")
        winter = wx[wx["service_date"].dt.month.isin([12, 1, 2, 3])]
        snow = band_summary(winter, "snowfall_in", [-0.01, 0, 1, 4, 100], ["None", "≤ 1″", "1–4″", "4″+"],
                            baseline="None")
        show(band_bars(snow))
        st.caption("Depth of new snow, before melting")

with temp_col:
    with st.container(key="card_temp"):
        card_title("Temperature", "By degrees above or below the month's average")
        temp = wx.assign(temp_vs_month=wx["avg_temperature_f"]
                         - wx.groupby("month")["avg_temperature_f"].transform("mean"))
        temps = band_summary(temp, "temp_vs_month", [-100, -10, -5, 5, 10, 100],
                             ["≤ −10°", "−10 to −5°", "± 5°", "+5 to +10°", "≥ +10°"], baseline="± 5°")
        show(band_bars(temps))
        st.caption("Daily mean temperature, (high + low) / 2, in °F")

# ══════════════════════════════════════════════════════════════════════════════
# 6. Footer
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="footer">
  <b>Sources</b> · MBTA V3 API (alerts, routes) · MBTA Gated Station Entries (ArcGIS Open Data) ·
  NOAA GHCN-Daily, Boston Logan (USW00014739)<br>
  <b>Refresh</b> · Page data hourly, from alerts checked every 15 minutes · Weather daily
  (NOAA posts ~3 days behind) · Ridership weekly (MBTA posts ~1–2 months behind)<br>
  <b>Method</b> · An incident groups the alerts the MBTA posts for one event (same route, cause,
  effect, and station, posted in close succession). Notices and facility issues (elevators,
  parking) are excluded. An alert ends at the end time the MBTA posted or when it leaves the MBTA's
  feed, whichever comes first. Ridership figures are averages per day, weekends and holidays
  included. "% vs typical" compares a day to the median for the same line, day of week, and month;
  the ~10 federal holidays a year are left out of those comparisons only, since a holiday isn't a
  typical day for its weekday.
</div>
""", unsafe_allow_html=True)
