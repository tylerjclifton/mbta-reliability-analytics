import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from google.cloud import bigquery

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="MBTA Reliability Analytics",
    page_icon="🚇",
    layout="wide",
)

# ── Dark theme ─────────────────────────────────────────────────────────────────

st.markdown("""
<style>
.stApp { background-color: #0e1117; color: #ffffff; }
[data-testid="stHeader"] { background-color: #0e1117; }
[data-testid="stSidebar"] { background-color: #161b22; }
section[data-testid="stMain"] { background-color: #0e1117; }
[data-testid="stMetric"] {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 16px;
}
[data-testid="stMetricLabel"] { color: #8b949e !important; font-size: 0.8rem; }
[data-testid="stMetricValue"] { color: #ffffff !important; }
hr { border-color: #30363d; }

/* Mobile / small-tablet: tighten padding and scale down text so KPI cards,
   the title, and tables stay readable once columns stack to full width. */
@media (max-width: 640px) {
    .block-container { padding: 1rem 0.75rem !important; }
    h1 { font-size: 1.6rem !important; }
    h2 { font-size: 1.35rem !important; }
    h3 { font-size: 1.15rem !important; }
    [data-testid="stMetric"] { padding: 10px; }
    [data-testid="stMetricValue"] { font-size: 1.3rem !important; }
    [data-testid="stMetricLabel"] { font-size: 0.7rem !important; }
}
</style>
""", unsafe_allow_html=True)

# ── Color maps ─────────────────────────────────────────────────────────────────

ROUTE_COLORS = {
    "Red":     "#DA291C",
    "Blue":    "#003DA5",
    "Orange":  "#ED8B00",
    "Green-B": "#00843D",
    "Green-C": "#00843D",
    "Green-D": "#00843D",
    "Green-E": "#00843D",
}

LINE_COLORS = {
    "Red Line":    "#DA291C",
    "Orange Line": "#ED8B00",
    "Blue Line":   "#003DA5",
    "Green Line":  "#00843D",
}

# Maps line-level display names to their underlying alert route_id values
LINE_TO_ROUTES = {
    "Red Line":    ["Red"],
    "Orange Line": ["Orange"],
    "Blue Line":   ["Blue"],
    "Green Line":  ["Green-B", "Green-C", "Green-D", "Green-E"],
}

ROUTE_TO_LINE = {
    "Red":     "Red Line",
    "Orange":  "Orange Line",
    "Blue":    "Blue Line",
    "Green-B": "Green Line",
    "Green-C": "Green Line",
    "Green-D": "Green Line",
    "Green-E": "Green Line",
}

DARK_LAYOUT = dict(
    paper_bgcolor="#0e1117",
    plot_bgcolor="#0e1117",
    font_color="#ffffff",
    xaxis=dict(gridcolor="#30363d", zerolinecolor="#30363d", fixedrange=True),
    yaxis=dict(gridcolor="#30363d", zerolinecolor="#30363d", fixedrange=True),
    legend=dict(
        bgcolor="#161b22", bordercolor="#30363d", borderwidth=1,
        orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5,
    ),
    margin=dict(t=90, b=30, l=10, r=10),
)

# Disables zoom/pan/toolbar on every chart — pinch-zoom and drag-to-pan
# fight with normal page scrolling on mobile, and add no value here since
# hover tooltips already surface exact values.
CHART_CONFIG = {"displayModeBar": False, "scrollZoom": False, "doubleClick": False}

def route_color(route_id):
    return ROUTE_COLORS.get(route_id, "#00843D")

def format_duration(minutes):
    """Format duration minutes as human-readable string."""
    if pd.isna(minutes) or minutes < 0:
        return "N/A"
    if minutes < 60:
        return f"{int(minutes)} min"
    if minutes < 1440:
        return f"{minutes/60:.1f} hrs"
    return f"{minutes/1440:.1f} days"

def format_last_updated(ts, include_time=False):
    """Format a UTC ingestion timestamp as an ET date (optionally with time)."""
    if pd.isna(ts):
        return "N/A"
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    ts_et = ts.tz_convert("America/New_York")
    return ts_et.strftime("%b %d, %Y %I:%M %p ET") if include_time else ts_et.strftime("%b %d, %Y")

# ── BigQuery client ───────────────────────────────────────────────────────────

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "mbta-reliability-analytics")

@st.cache_resource
def get_client():
    return bigquery.Client(project=PROJECT_ID)

# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_alerts():
    client = get_client()
    query = f"""
        SELECT
            alert_id,
            route_id,
            route_name,
            alert_start_date,
            alert_end_date,
            alert_start_ts,
            alert_end_ts,
            alert_duration_minutes,
            alert_header,
            alert_description,
            alert_cause,
            alert_effect,
            alert_severity,
            ingestion_timestamp
        FROM `{PROJECT_ID}.gold.rail_alerts`
        ORDER BY alert_start_date DESC
    """
    return client.query(query).to_dataframe()

@st.cache_data(ttl=3600)
def load_ridership():
    client = get_client()
    query = f"""
        SELECT
            service_date,
            route_name,
            ridership,
            line_alert_count,
            avg_temperature_f,
            max_temperature_f,
            total_precipitation_mm,
            avg_wind_speed_mph,
            avg_humidity_percent,
            min_visibility_miles
        FROM `{PROJECT_ID}.gold.rail_ridership`
        ORDER BY service_date DESC
    """
    return client.query(query).to_dataframe()

# ── Load data ─────────────────────────────────────────────────────────────────

with st.spinner("Loading data..."):
    df_alerts    = load_alerts()
    df_ridership = load_ridership()

if df_alerts.empty:
    st.warning("No data available yet.")
    st.stop()

df_alerts["alert_start_date"] = pd.to_datetime(df_alerts["alert_start_date"])
df_alerts["alert_end_date"]   = pd.to_datetime(df_alerts["alert_end_date"])
df_alerts["alert_start_ts"]   = pd.to_datetime(df_alerts["alert_start_ts"], utc=True)
df_alerts["alert_end_ts"]     = pd.to_datetime(df_alerts["alert_end_ts"], utc=True)
df_ridership["service_date"]  = pd.to_datetime(df_ridership["service_date"])

today  = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)
now_ts = pd.Timestamp.now(tz="UTC")

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown(
    "<h1 style='text-align:center; color:#ffffff;'>🚇 MBTA Reliability Analytics</h1>",
    unsafe_allow_html=True,
)

# ── Global filters ──────────────────────────────────────────────────────────

all_lines      = ["Red Line", "Orange Line", "Blue Line", "Green Line"]
selected_lines = st.multiselect("Filter by Route", all_lines, default=all_lines)

selected_route_ids = [r for line in selected_lines for r in LINE_TO_ROUTES[line]]
filtered_alerts    = df_alerts[df_alerts["route_id"].isin(selected_route_ids)]

# TTM window — applied to all charts
year_start  = today - pd.DateOffset(months=12)
year_alerts = filtered_alerts[filtered_alerts["alert_start_date"] >= year_start]

# Ridership: TTM anchored to latest available date
_max_ridership_date    = df_ridership["service_date"].max() if not df_ridership.empty else today
_ridership_window_start = _max_ridership_date - pd.DateOffset(months=12)
filtered_ridership = df_ridership[
    df_ridership["route_name"].isin(selected_lines) &
    (df_ridership["service_date"] >= _ridership_window_start)
]

# Stable cause color order — computed once so both cause charts use matching colors
cause_order = sorted(filtered_alerts["alert_cause"].dropna().unique().tolist())

_alerts_updated = pd.to_datetime(df_alerts["ingestion_timestamp"]).max()

st.caption("All data and charts reflect the trailing 12 months")
st.caption(f"Alerts updated {format_last_updated(_alerts_updated, include_time=True)}")

# ── KPI row ───────────────────────────────────────────────────────────────────

active_alerts = filtered_alerts[
    (filtered_alerts["alert_start_ts"] <= now_ts) &
    (filtered_alerts["alert_end_ts"].isna() | (filtered_alerts["alert_end_ts"] >= now_ts))
]
upcoming_alerts = filtered_alerts[filtered_alerts["alert_start_ts"] > now_ts]

st.divider()
k1, k2, k3, k4 = st.columns(4)
k1.metric("Active Alerts",   f"{len(active_alerts):,}")
k2.metric("Upcoming Alerts", f"{len(upcoming_alerts):,}")
k3.metric("Impacted Routes", f"{active_alerts['route_id'].nunique()}")
median_dur = df_alerts["alert_duration_minutes"].median()
k4.metric("Median Alert Duration", format_duration(median_dur))
st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# ALERTS SECTION
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("<h2 style='text-align:center'>🚨 Alerts</h2>", unsafe_allow_html=True)
st.divider()

def _alert_table(df):
    display = df[[
        "route_id", "alert_effect", "alert_cause",
        "alert_start_date", "alert_end_date", "alert_duration_minutes",
        "alert_header", "alert_description",
    ]].rename(columns={
        "route_id": "Route", "alert_effect": "Effect", "alert_cause": "Cause",
        "alert_start_date": "Start", "alert_end_date": "End",
        "alert_duration_minutes": "Duration",
        "alert_header": "Header", "alert_description": "Description",
    }).copy()
    display["Start"] = display["Start"].dt.date
    display["End"]   = display["End"].apply(lambda x: x.date() if pd.notna(x) else "Ongoing")
    display["Duration"] = display["Duration"].apply(format_duration)
    return display

# Active alerts table
st.subheader("Active Alerts")
if active_alerts.empty:
    st.info("No active alerts right now.")
else:
    st.dataframe(_alert_table(active_alerts), use_container_width=True, hide_index=True)

st.divider()

# Upcoming alerts table — scheduled to start in the future
st.subheader("Upcoming Alerts")
if upcoming_alerts.empty:
    st.info("No upcoming alerts scheduled.")
else:
    st.dataframe(_alert_table(upcoming_alerts), use_container_width=True, hide_index=True)

st.divider()

# Alerts by route + by month
al_c1, al_c2 = st.columns(2)
with al_c1:
    st.subheader("Alerts by Route")
    route_counts = (
        year_alerts
        .groupby("route_id").size().reset_index(name="alert_count")
    )
    fig = px.bar(
        route_counts, x="route_id", y="alert_count",
        color="route_id", color_discrete_map=ROUTE_COLORS,
        labels={"route_id": "Route", "alert_count": "Alerts"},
    )
    fig.update_layout(**DARK_LAYOUT)
    fig.update_yaxes(tickformat="d", rangemode="tozero")
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)

with al_c2:
    st.subheader("Alerts by Month")
    monthly_df = year_alerts.copy()
    monthly_df["month"] = monthly_df["alert_start_date"].dt.to_period("M").dt.to_timestamp()
    monthly = monthly_df.groupby("month").size().reset_index(name="alert_count")
    fig = px.bar(
        monthly, x="month", y="alert_count",
        color_discrete_sequence=["#80276C"],
        labels={"month": "Month", "alert_count": "Alerts"},
    )
    fig.update_layout(**DARK_LAYOUT)
    fig.update_yaxes(tickformat="d", rangemode="tozero")
    fig.update_xaxes(dtick="M1", tickformat="%b %Y", tickangle=-45)
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)

st.divider()

# Cause share + Effect share side by side
cs_c1, cs_c2 = st.columns(2)
with cs_c1:
    st.subheader("Alerts by Cause")
    causes = (
        year_alerts.groupby("alert_cause").size()
        .reset_index(name="count").sort_values("count", ascending=False).head(10)
    )
    fig = px.pie(
        causes, names="alert_cause", values="count", hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Set2,
        category_orders={"alert_cause": cause_order},
    )
    fig.update_traces(textfont_color="white")
    fig.update_layout(**{**DARK_LAYOUT, "showlegend": True})
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)

with cs_c2:
    st.subheader("Alerts by Effect")
    effects = (
        year_alerts.groupby("alert_effect").size()
        .reset_index(name="count").sort_values("count", ascending=False).head(10)
    )
    effect_order = sorted(year_alerts["alert_effect"].dropna().unique().tolist())
    fig = px.pie(
        effects, names="alert_effect", values="count", hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Pastel,
        category_orders={"alert_effect": effect_order},
    )
    fig.update_traces(textfont_color="white")
    fig.update_layout(**{**DARK_LAYOUT, "showlegend": True})
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)

# Median duration by cause + effect — side by side horizontal bars.
# Median (not mean) because a handful of multi-year construction alerts
# would otherwise dominate the average and misrepresent typical duration.
dur_c1, dur_c2 = st.columns(2)
with dur_c1:
    st.subheader("Median Alert Duration by Cause")
    dur_cause = (
        year_alerts.dropna(subset=["alert_duration_minutes", "alert_cause"])
        .groupby("alert_cause")["alert_duration_minutes"]
        .median()
        .reset_index(name="median_minutes")
        .sort_values("median_minutes", ascending=True)
    )
    if not dur_cause.empty:
        dur_cause["median_display"] = dur_cause["median_minutes"].apply(format_duration)
        fig = px.bar(
            dur_cause, x="median_minutes", y="alert_cause",
            orientation="h",
            color_discrete_sequence=["#80276C"],
            labels={"median_minutes": "Median Duration", "alert_cause": ""},
            text="median_display",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(**DARK_LAYOUT)
        fig.update_xaxes(visible=False, range=[0, dur_cause["median_minutes"].max() * 1.2])
        st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
    else:
        st.info("No data.")

with dur_c2:
    st.subheader("Median Alert Duration by Effect")
    dur_effect = (
        year_alerts.dropna(subset=["alert_duration_minutes", "alert_effect"])
        .groupby("alert_effect")["alert_duration_minutes"]
        .median()
        .reset_index(name="median_minutes")
        .sort_values("median_minutes", ascending=True)
    )
    if not dur_effect.empty:
        dur_effect["median_display"] = dur_effect["median_minutes"].apply(format_duration)
        fig = px.bar(
            dur_effect, x="median_minutes", y="alert_effect",
            orientation="h",
            color_discrete_sequence=["#0e7c7b"],
            labels={"median_minutes": "Median Duration", "alert_effect": ""},
            text="median_display",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(**DARK_LAYOUT)
        fig.update_xaxes(visible=False, range=[0, dur_effect["median_minutes"].max() * 1.2])
        st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
    else:
        st.info("No data.")

st.divider()

# Cause breakdown by route — normalized to % so routes with fewer alerts are still comparable
cr_c1, cr_c2 = st.columns(2)
with cr_c1:
    st.subheader("Cause Distribution by Route")
    cause_route_grp = year_alerts.groupby(["route_id", "alert_cause"]).size().reset_index(name="count")
    if not cause_route_grp.empty:
        totals = cause_route_grp.groupby("route_id")["count"].transform("sum")
        cause_route_grp["pct"] = (cause_route_grp["count"] / totals * 100).round(1)
        fig = px.bar(
            cause_route_grp, x="route_id", y="pct",
            color="alert_cause", barmode="stack",
            color_discrete_sequence=px.colors.qualitative.Set2,
            category_orders={"alert_cause": cause_order},
            labels={"route_id": "Route", "pct": "% of Alerts", "alert_cause": "Cause"},
            text="pct",
        )
        fig.update_traces(texttemplate="%{text:.0f}%", textposition="inside")
        fig.update_layout(**DARK_LAYOUT)
        fig.update_yaxes(range=[0, 100], ticksuffix="%")
        st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
    else:
        st.info("No data.")

with cr_c2:
    st.subheader("Effect Distribution by Route")
    effect_route_grp = year_alerts.groupby(["route_id", "alert_effect"]).size().reset_index(name="count")
    if not effect_route_grp.empty:
        totals = effect_route_grp.groupby("route_id")["count"].transform("sum")
        effect_route_grp["pct"] = (effect_route_grp["count"] / totals * 100).round(1)
        effect_order = sorted(year_alerts["alert_effect"].dropna().unique().tolist())
        fig = px.bar(
            effect_route_grp, x="route_id", y="pct",
            color="alert_effect", barmode="stack",
            color_discrete_sequence=px.colors.qualitative.Pastel,
            category_orders={"alert_effect": effect_order},
            labels={"route_id": "Route", "pct": "% of Alerts", "alert_effect": "Effect"},
            text="pct",
        )
        fig.update_traces(texttemplate="%{text:.0f}%", textposition="inside")
        fig.update_layout(**DARK_LAYOUT)
        fig.update_yaxes(range=[0, 100], ticksuffix="%")
        st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
    else:
        st.info("No data.")

st.divider()

# Cause → Effect heatmap
st.subheader("Cause & Effect Matrix")
heat_df = (
    year_alerts
    .groupby(["alert_cause", "alert_effect"])
    .size()
    .reset_index(name="count")
)
if not heat_df.empty:
    heat_pivot = heat_df.pivot(index="alert_cause", columns="alert_effect", values="count").fillna(0)
    fig = px.imshow(
        heat_pivot,
        color_continuous_scale=[[0, "#f5e8f5"], [0.5, "#80276C"], [1.0, "#2d0a2d"]],
        text_auto=True,
        aspect="auto",
        labels={"x": "Effect", "y": "Cause", "color": "Alerts"},
    )
    fig.update_layout(
        **DARK_LAYOUT,
        coloraxis_colorbar=dict(title="Alerts", tickfont=dict(color="#ffffff")),
        xaxis_tickangle=-45,
    )
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
else:
    st.info("No data.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# RIDERSHIP SECTION
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("<h2 style='text-align:center'>🚃 Ridership</h2>", unsafe_allow_html=True)

if df_ridership.empty:
    st.info("No ridership data available yet.")
else:
    st.divider()

    # Ridership over time with alert count overlay — aggregated to monthly
    st.subheader("Alert Impact on Ridership")

    monthly_r = filtered_ridership.copy()
    monthly_r["month"] = monthly_r["service_date"].dt.to_period("M").dt.to_timestamp()
    monthly_r = monthly_r.groupby(["month", "route_name"]).agg(
        ridership=("ridership", "sum"),
        line_alert_count=("line_alert_count", "mean"),
    ).reset_index()

    fig = go.Figure()
    for line in selected_lines:
        line_data = monthly_r[monthly_r["route_name"] == line].sort_values("month")
        color = LINE_COLORS.get(line, "#888888")
        fig.add_trace(go.Bar(
            name=line,
            x=line_data["month"],
            y=line_data["ridership"],
            marker_color=color,
            opacity=1.0,
            yaxis="y1",
        ))
        fig.add_trace(go.Scatter(
            name=f"{line} Alerts",
            x=line_data["month"],
            y=line_data["line_alert_count"],
            mode="lines",
            line=dict(color=color, dash="dot", width=2),
            yaxis="y2",
        ))

    fig.update_layout(**DARK_LAYOUT)
    fig.update_layout(
        barmode="group",
        yaxis=dict(title="Ridership", gridcolor="#30363d", rangemode="tozero"),
        yaxis2=dict(
            title="Active Alerts", overlaying="y", side="right",
            rangemode="tozero", gridcolor="rgba(0,0,0,0)",
            dtick=1, tickformat="d",
        ),
    )
    fig.update_xaxes(dtick="M1", tickformat="%b %Y", tickangle=-45)
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)

    st.divider()

    # Day of week ridership
    st.subheader("Average Ridership by Day")
    dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow_df = filtered_ridership.copy()
    dow_df["day_of_week"] = dow_df["service_date"].dt.day_name()
    dow = dow_df.groupby(["day_of_week", "route_name"])["ridership"].mean().reset_index()
    dow["day_of_week"] = pd.Categorical(dow["day_of_week"], categories=dow_order, ordered=True)
    dow = dow.sort_values("day_of_week")
    fig = px.bar(
        dow, x="day_of_week", y="ridership",
        color="route_name", barmode="group",
        color_discrete_map=LINE_COLORS,
        labels={"day_of_week": "Day", "ridership": "Ridership", "route_name": "Line"},
    )
    fig.update_layout(**DARK_LAYOUT)
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)

    st.divider()

    # Weather correlations
    wx_c1, wx_c2 = st.columns(2)
    with wx_c1:
        st.subheader("Temperature vs Ridership")
        temp_df = filtered_ridership.dropna(subset=["avg_temperature_f"])
        if not temp_df.empty:
            fig = px.scatter(
                temp_df, x="avg_temperature_f", y="ridership",
                color="route_name", color_discrete_map=LINE_COLORS,
                trendline="ols", trendline_scope="overall",
                trendline_color_override="#ff6b6b",
                labels={"avg_temperature_f": "Avg Temperature (°F)",
                        "ridership": "Daily Ridership", "route_name": "Line"},
            )
            fig.update_layout(**DARK_LAYOUT)
            st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
        else:
            st.info("Temperature data not yet available.")

    with wx_c2:
        st.subheader("Precipitation vs Ridership")
        prec_df = filtered_ridership.dropna(subset=["total_precipitation_mm"])
        if not prec_df.empty:
            fig = px.scatter(
                prec_df, x="total_precipitation_mm", y="ridership",
                color="route_name", color_discrete_map=LINE_COLORS,
                trendline="ols", trendline_scope="overall",
                trendline_color_override="#ff6b6b",
                labels={"total_precipitation_mm": "Total Precipitation (mm)",
                        "ridership": "Daily Ridership", "route_name": "Line"},
            )
            fig.update_layout(**DARK_LAYOUT)
            st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
        else:
            st.info("Precipitation data not yet available.")

# ── Footer ────────────────────────────────────────────────────────────────────

st.divider()
st.caption("Sources: MBTA Alerts API · NWS Weather API · MBTA ArcGIS Open Data")
st.caption("Cadence: Alerts refresh hourly · Weather refreshes daily at 6AM ET · Ridership refreshes quarterly (~1–2 month delay)")