import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="MBTA Reliability Analytics",
    page_icon="🚇",
    layout="wide",
)

# ── Dark theme + route-colored table rows ─────────────────────────────────────

st.markdown("""
<style>
/* Dark background */
.stApp { background-color: #0e1117; color: #ffffff; }
[data-testid="stHeader"] { background-color: #0e1117; }
[data-testid="stSidebar"] { background-color: #161b22; }
section[data-testid="stMain"] { background-color: #0e1117; }

/* Metric cards */
[data-testid="stMetric"] {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 16px;
}
[data-testid="stMetricLabel"] { color: #8b949e !important; font-size: 0.8rem; }
[data-testid="stMetricValue"] { color: #ffffff !important; }

/* Dividers */
hr { border-color: #30363d; }

/* Route-colored table rows */
.route-Red    { color: #DA291C !important; font-weight: 600; }
.route-Blue   { color: #003DA5 !important; font-weight: 600; }
.route-Orange { color: #ED8B00 !important; font-weight: 600; }
.route-Green  { color: #00843D !important; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ── Route color map ───────────────────────────────────────────────────────────

ROUTE_COLORS = {
    "Red":     "#DA291C",
    "Blue":    "#003DA5",
    "Orange":  "#ED8B00",
    "Green-B": "#00843D",
    "Green-C": "#00843D",
    "Green-D": "#00843D",
    "Green-E": "#00843D",
}

DARK_LAYOUT = dict(
    paper_bgcolor="#0e1117",
    plot_bgcolor="#0e1117",
    font_color="#ffffff",
    xaxis=dict(gridcolor="#30363d", zerolinecolor="#30363d"),
    yaxis=dict(gridcolor="#30363d", zerolinecolor="#30363d"),
    legend=dict(bgcolor="#161b22", bordercolor="#30363d", borderwidth=1),
    margin=dict(t=30, b=30, l=10, r=10),
)

def route_color(route_id):
    if route_id == "Red":    return "#DA291C"
    if route_id == "Blue":   return "#003DA5"
    if route_id == "Orange": return "#ED8B00"
    return "#00843D"  # all Green branches

# ── BigQuery client ───────────────────────────────────────────────────────────

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "mbta-reliability-analytics")
KEYFILE    = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

@st.cache_resource
def get_client():
    if KEYFILE:
        creds = service_account.Credentials.from_service_account_file(KEYFILE)
        return bigquery.Client(project=PROJECT_ID, credentials=creds)
    return bigquery.Client(project=PROJECT_ID)

# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_alerts():
    client = get_client()
    query = f"""
        SELECT
            alert_start_date,
            alert_end_date,
            alert_id,
            route_id,
            route_name,
            alert_header,
            alert_description,
            alert_cause,
            alert_effect,
            avg_temperature_f
        FROM `{PROJECT_ID}.gold.mbta_alerts_with_weather`
        WHERE alert_start_date IS NOT NULL
        ORDER BY alert_start_date DESC
    """
    return client.query(query).to_dataframe()

# ── Load + prep data ──────────────────────────────────────────────────────────

with st.spinner("Loading data..."):
    df = load_alerts()

if df.empty:
    st.warning("No data available yet. The ingestion pipeline may still be accumulating data.")
    st.stop()

df["alert_start_date"] = pd.to_datetime(df["alert_start_date"])
df["alert_end_date"]   = pd.to_datetime(df["alert_end_date"])
df["duration_days"]    = (df["alert_end_date"] - df["alert_start_date"]).dt.days.clip(lower=0)

today       = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)
month_start = today.replace(day=1)

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown(
    "<h1 style='text-align:center; color:#ffffff;'>🚇 MBTA Alerts</h1>",
    unsafe_allow_html=True,
)

# ── Filters ───────────────────────────────────────────────────────────────────

col_f1, col_f2 = st.columns(2)
with col_f1:
    routes = sorted(df["route_id"].dropna().unique())
    selected_routes = st.multiselect("Routes", routes, default=routes)
with col_f2:
    min_date = df["alert_start_date"].min().date()
    max_date = df["alert_start_date"].max().date()
    date_range = st.date_input("Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date)

if len(date_range) == 2:
    start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
    filtered = df[
        df["route_id"].isin(selected_routes) &
        (df["alert_start_date"] >= start) &
        (df["alert_start_date"] <= end)
    ]
else:
    filtered = df[df["route_id"].isin(selected_routes)]

# ── KPI row ───────────────────────────────────────────────────────────────────

st.divider()
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Alerts", f"{len(filtered):,}")
k2.metric("Routes Affected", f"{filtered['route_id'].nunique()}")
avg_dur = filtered["duration_days"].mean()
k3.metric("Avg Alert Duration", f"{avg_dur:.1f} days" if pd.notna(avg_dur) else "N/A")
avg_tmp = filtered["avg_temperature_f"].mean()
k4.metric("Avg Temp on Alert Days", f"{avg_tmp:.1f} °F" if pd.notna(avg_tmp) else "N/A")
st.divider()

# ── Active Alerts table ───────────────────────────────────────────────────────

st.subheader("Active Alerts")

today_alerts = filtered[filtered["alert_end_date"].isna() | (filtered["alert_end_date"] >= today)]

if today_alerts.empty:
    st.info("No active alerts right now.")
else:
    table_cols = ["route_id", "alert_header", "alert_description", "alert_cause", "alert_effect", "alert_start_date", "alert_end_date"]
    display    = today_alerts[table_cols].rename(columns={
        "route_id":          "Route",
        "alert_header":      "Header",
        "alert_description": "Description",
        "alert_cause":       "Cause",
        "alert_effect":      "Effect",
        "alert_start_date":  "Start",
        "alert_end_date":    "End",
    })

    def color_row(row):
        color = route_color(row["Route"])
        return [f"color: {color}"] * len(row)

    st.dataframe(
        display.style.apply(color_row, axis=1),
        use_container_width=True,
        hide_index=True,
    )

st.divider()

# ── Alerts By Line — running total current month ──────────────────────────────

st.subheader("Alerts By Line (Running Total — Current Month)")

month_df = filtered[filtered["alert_start_date"] >= month_start].copy()

if month_df.empty:
    st.info("No alerts yet this month.")
else:
    month_df["day"] = month_df["alert_start_date"].dt.normalize()
    cumulative = (
        month_df.groupby(["day", "route_id"])
        .size()
        .reset_index(name="daily_count")
        .sort_values(["route_id", "day"])
    )
    cumulative["running_total"] = cumulative.groupby("route_id")["daily_count"].cumsum()

    fig_cum = px.line(
        cumulative,
        x="day",
        y="running_total",
        color="route_id",
        color_discrete_map=ROUTE_COLORS,
        labels={"day": "", "running_total": "Cumulative Alerts", "route_id": "Route"},
        line_shape="linear",
    )
    fig_cum.update_traces(line_width=2.5)
    fig_cum.update_layout(**DARK_LAYOUT)
    st.plotly_chart(fig_cum, use_container_width=True)

st.divider()

# ── Alert Causes pie + Alert Cause x Temperature ─────────────────────────────

row2_l, row2_r = st.columns(2)

with row2_l:
    st.subheader("Alert Causes")
    causes = (
        filtered.groupby("alert_cause")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .head(10)
    )
    fig_pie = px.pie(
        causes,
        names="alert_cause",
        values="count",
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig_pie.update_traces(textfont_color="white")
    fig_pie.update_layout(**{**DARK_LAYOUT, "showlegend": True})
    st.plotly_chart(fig_pie, use_container_width=True)

with row2_r:
    st.subheader("Alert Cause × Temperature")
    temp_df = filtered.dropna(subset=["avg_temperature_f"]).copy()
    if not temp_df.empty:
        bins   = [float("-inf"), 32, 55, 75, float("inf")]
        labels = ["Freezing (≤32°F)", "Cold (33–55°F)", "Mild (56–75°F)", "Hot (>75°F)"]
        temp_df["temp_bucket"] = pd.cut(temp_df["avg_temperature_f"], bins=bins, labels=labels)
        cause_temp = (
            temp_df.groupby(["alert_cause", "temp_bucket"], observed=True)
            .size()
            .reset_index(name="count")
        )
        fig_ct = px.bar(
            cause_temp,
            x="alert_cause",
            y="count",
            color="temp_bucket",
            barmode="stack",
            labels={"alert_cause": "Cause", "count": "Alerts", "temp_bucket": "Temp Range"},
            color_discrete_sequence=["#4e9af1", "#74b9ff", "#fdcb6e", "#e17055"],
        )
        fig_ct.update_layout(**{**DARK_LAYOUT, "xaxis_tickangle": -30})
        st.plotly_chart(fig_ct, use_container_width=True)
    else:
        st.info("Weather data not yet joined.")

st.divider()

# ── Alerts over time (weekly, by route) ──────────────────────────────────────

st.subheader("Alerts Over Time")
filtered["week"] = filtered["alert_start_date"].dt.to_period("W").apply(lambda p: p.start_time)
weekly = (
    filtered.groupby(["week", "route_id"])
    .size()
    .reset_index(name="alert_count")
)
fig_line = px.line(
    weekly,
    x="week",
    y="alert_count",
    color="route_id",
    color_discrete_map=ROUTE_COLORS,
    labels={"week": "", "alert_count": "Alerts", "route_id": "Route"},
)
fig_line.update_traces(line_width=2.5)
fig_line.update_layout(**DARK_LAYOUT)
st.plotly_chart(fig_line, use_container_width=True)

# ── Footer ────────────────────────────────────────────────────────────────────

st.divider()
st.caption(
    f"Data refreshed twice daily at 7am & 7pm ET · "
    f"{len(df):,} total records · "
    "Source: MBTA Alerts API + NWS Boston Logan Airport (KBOS)"
)
