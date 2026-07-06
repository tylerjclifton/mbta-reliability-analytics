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
    "Green-B": "#005A28",
    "Green-C": "#00843D",
    "Green-D": "#4DBD74",
    "Green-E": "#93D6A8",
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
    if route_id == "Red":     return "#DA291C"
    if route_id == "Blue":    return "#003DA5"
    if route_id == "Orange":  return "#ED8B00"
    if route_id == "Green-B": return "#005A28"
    if route_id == "Green-C": return "#00843D"
    if route_id == "Green-D": return "#4DBD74"
    if route_id == "Green-E": return "#93D6A8"
    return "#00843D"  # fallback

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
            avg_temperature_f,
            avg_precipitation_mm,
            max_precipitation_mm,
            avg_wind_speed_mph,
            max_wind_speed_mph,
            avg_visibility_miles
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
    "<h1 style='text-align:center; color:#ffffff;'>🚇 MBTA Reliability Analytics</h1>",
    unsafe_allow_html=True,
)

# ── Filters ───────────────────────────────────────────────────────────────────

col_f1, col_f2 = st.columns(2)
with col_f1:
    routes = sorted(df["route_id"].dropna().unique())
    selected_routes = st.multiselect("Routes", routes, default=routes)
with col_f2:
    effects = sorted(df["alert_effect"].dropna().unique())
    selected_effects = st.multiselect("Alert Effect", effects, default=effects)

filtered = df[
    df["route_id"].isin(selected_routes) &
    df["alert_effect"].isin(selected_effects)
]

# ── KPI row ───────────────────────────────────────────────────────────────────

active_alerts = filtered[filtered["alert_end_date"].isna() | (filtered["alert_end_date"] >= today)]
month_alerts  = filtered[filtered["alert_start_date"] >= month_start]

st.divider()
k1, k2, k3, k4 = st.columns(4)
k1.metric("Active Alerts",             f"{len(active_alerts):,}")
k2.metric("Routes Currently Affected", f"{active_alerts['route_id'].nunique()}")
k3.metric("Alerts This Month",         f"{len(month_alerts):,}")
avg_dur = filtered["duration_days"].mean()
k4.metric("Avg Alert Duration",        f"{avg_dur:.1f} days" if pd.notna(avg_dur) else "N/A")
st.divider()

# ── Active Alerts Table ───────────────────────────────────────────────────────

st.subheader("Active Alerts")

today_alerts = active_alerts

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

# ── Alert History Table ───────────────────────────────────────────────────────

st.subheader("Alert History")

hist_c1, hist_c2 = st.columns(2)
with hist_c1:
    hist_min = df["alert_start_date"].min().date()
    hist_max = df["alert_start_date"].max().date()
    hist_dates = st.date_input(
        "Date Range",
        value=(hist_min, hist_max),
        min_value=hist_min,
        max_value=hist_max,
        key="hist_dates",
    )
with hist_c2:
    search_text = st.text_input("Search Header / Description", key="hist_search")

if len(hist_dates) == 2:
    h_start = pd.Timestamp(hist_dates[0])
    h_end   = pd.Timestamp(hist_dates[1])
    history = filtered[
        (filtered["alert_start_date"] >= h_start) &
        (filtered["alert_start_date"] <= h_end)
    ].copy()
else:
    history = filtered.copy()

if search_text:
    mask = (
        history["alert_header"].str.contains(search_text, case=False, na=False) |
        history["alert_description"].str.contains(search_text, case=False, na=False)
    )
    history = history[mask]

hist_display = history[
    ["route_id", "alert_header", "alert_description", "alert_cause",
     "alert_effect", "alert_start_date", "alert_end_date", "duration_days"]
].rename(columns={
    "route_id":          "Route",
    "alert_header":      "Header",
    "alert_description": "Description",
    "alert_cause":       "Cause",
    "alert_effect":      "Effect",
    "alert_start_date":  "Start",
    "alert_end_date":    "End",
    "duration_days":     "Duration (days)",
})

def color_hist_row(row):
    color = route_color(row["Route"])
    return [f"color: {color}"] * len(row)

st.caption(f"{len(history):,} alerts")
st.dataframe(
    hist_display.style.apply(color_hist_row, axis=1),
    use_container_width=True,
    hide_index=True,
    height=400,
)

st.divider()

# ── Alerts By Route Bar + Alerts By Month Bar ───────────────────────────────────────

time_col1, time_col2 = st.columns(2)

with time_col1:
    st.subheader("Alerts By Route")

    all_routes = sorted(df["route_id"].dropna().unique())
    route_counts = filtered.groupby("route_id").size().reset_index(name="alert_count")
    all_routes_df = pd.DataFrame({"route_id": all_routes})
    route_counts = all_routes_df.merge(route_counts, on="route_id", how="left").fillna(0)
    route_counts["alert_count"] = route_counts["alert_count"].astype(int)

    fig_bar = px.bar(
        route_counts,
        x="route_id",
        y="alert_count",
        color="route_id",
        color_discrete_map=ROUTE_COLORS,
        labels={"route_id": "Route", "alert_count": "Alerts"},
    )
    fig_bar.update_layout(**DARK_LAYOUT)
    fig_bar.update_yaxes(tickformat="d", rangemode="tozero")
    st.plotly_chart(fig_bar, use_container_width=True)

with time_col2:
    st.subheader("Alerts By Month")

    if not filtered.empty:
        monthly_df = filtered.copy()
        monthly_df["month"] = monthly_df["alert_start_date"].dt.to_period("M").dt.to_timestamp()
        monthly = (
            monthly_df.groupby(["month", "route_id"])
            .size()
            .reset_index(name="alert_count")
        )
        fig_monthly = px.bar(
            monthly,
            x="month",
            y="alert_count",
            color="route_id",
            barmode="stack",
            color_discrete_map=ROUTE_COLORS,
            labels={"month": "Month", "alert_count": "Alerts", "route_id": "Route"},
        )
        fig_monthly.update_layout(**DARK_LAYOUT)
        fig_monthly.update_yaxes(tickformat="d", rangemode="tozero")
        # Default view: last 12 months — user can zoom/pan to see full history
        view_start = today - pd.DateOffset(months=12)
        fig_monthly.update_xaxes(
            range=[view_start, today + pd.DateOffset(months=1)],
            dtick="M1", tickformat="%b %Y", tickangle=-30,
        )
        st.plotly_chart(fig_monthly, use_container_width=True)
    else:
        st.info("No data to display.")

st.divider()

# ── Alert Cause Share Pie + Alerts By Cause Bar ─────────────────────────────────

row2_l, row2_r = st.columns(2)

with row2_l:
    st.subheader("Alert Cause Share")
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
    st.subheader("Alerts By Cause")
    cause_route = (
        filtered.groupby(["alert_cause", "route_id"])
        .size()
        .reset_index(name="count")
    )
    if not cause_route.empty:
        fig_cr = px.bar(
            cause_route,
            x="alert_cause",
            y="count",
            color="route_id",
            barmode="stack",
            color_discrete_map=ROUTE_COLORS,
            labels={"alert_cause": "Cause", "count": "Alerts", "route_id": "Route"},
        )
        fig_cr.update_layout(**{**DARK_LAYOUT, "xaxis_tickangle": -30})
        st.plotly_chart(fig_cr, use_container_width=True)
    else:
        st.info("No alert data available.")

st.divider()

# ── Weather Impact Scatters ───────────────────────────────────────────────────

wx_col1, wx_col2 = st.columns(2)

with wx_col1:
    st.subheader("Alerts vs Temperature")
    scatter_df = filtered.dropna(subset=["avg_temperature_f"]).copy()
    if not scatter_df.empty:
        daily_temp = (
            scatter_df.groupby("alert_start_date")
            .agg(
                alert_count=("alert_id", "count"),
                avg_temp=("avg_temperature_f", "first"),
            )
            .reset_index()
        )
        fig_scatter = px.scatter(
            daily_temp,
            x="avg_temp",
            y="alert_count",
            trendline="ols",
            trendline_color_override="#ff6b6b",
            labels={"avg_temp": "Avg Temperature (°F)", "alert_count": "Alerts"},
        )
        fig_scatter.update_traces(
            selector=dict(mode="markers"),
            marker=dict(color="#4e9af1", size=8, opacity=0.7),
        )
        fig_scatter.update_layout(**DARK_LAYOUT)
        fig_scatter.update_yaxes(tickformat="d", rangemode="tozero")
        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info("Weather data not yet joined.")

with wx_col2:
    st.subheader("Alerts vs Precipitation")
    prec_df = filtered.dropna(subset=["avg_precipitation_mm"]).copy()
    if not prec_df.empty:
        daily_prec = (
            prec_df.groupby("alert_start_date")
            .agg(
                alert_count=("alert_id", "count"),
                avg_precip=("avg_precipitation_mm", "first"),
            )
            .reset_index()
        )
        fig_prec = px.scatter(
            daily_prec,
            x="avg_precip",
            y="alert_count",
            trendline="ols",
            trendline_color_override="#ff6b6b",
            labels={"avg_precip": "Avg Precipitation (mm)", "alert_count": "Alerts"},
        )
        fig_prec.update_traces(
            selector=dict(mode="markers"),
            marker=dict(color="#74b9ff", size=8, opacity=0.7),
        )
        fig_prec.update_layout(**DARK_LAYOUT)
        fig_prec.update_yaxes(tickformat="d", rangemode="tozero")
        st.plotly_chart(fig_prec, use_container_width=True)
    else:
        st.info("Precipitation data not yet available.")

# ── Footer ────────────────────────────────────────────────────────────────────

st.divider()
st.caption(
    f"Data refreshed twice daily at 7 AM and 7 PM EST. "
    f"{len(df):,} total records. "
    "Source: MBTA (Alerts, Routes) API + NWS (Weather) API"
)
