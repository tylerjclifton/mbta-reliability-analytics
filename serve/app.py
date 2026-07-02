import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account

# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="MBTA Reliability Analytics",
    page_icon="🚇",
    layout="wide",
)

# ── BigQuery client ───────────────────────────────────────────────────────────

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "mbta-reliability-analytics")
KEYFILE    = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

@st.cache_resource
def get_client():
    if KEYFILE:
        creds = service_account.Credentials.from_service_account_file(KEYFILE)
        return bigquery.Client(project=PROJECT_ID, credentials=creds)
    return bigquery.Client(project=PROJECT_ID)  # uses attached service account on Cloud Run

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
            alert_cause,
            alert_effect,
            alert_severity,
            avg_temperature_f,
            avg_precipitation_mm,
            avg_wind_speed_mph,
            avg_visibility_miles,
            avg_humidity_percent
        FROM `{PROJECT_ID}.gold.mbta_alerts_with_weather`
        WHERE alert_start_date IS NOT NULL
        ORDER BY alert_start_date DESC
    """
    return client.query(query).to_dataframe()

# ── Load data ─────────────────────────────────────────────────────────────────

with st.spinner("Loading data..."):
    df = load_alerts()

if df.empty:
    st.warning("No data available yet. The ingestion pipeline may still be accumulating data.")
    st.stop()

df["alert_start_date"] = pd.to_datetime(df["alert_start_date"])
df["week"] = df["alert_start_date"].dt.to_period("W").apply(lambda p: p.start_time)

# ── Header ────────────────────────────────────────────────────────────────────

st.title("🚇 MBTA Reliability Analytics")
st.caption(
    "Analyzing service disruptions on the Red, Blue, Orange, and Green Lines "
    "and their relationship with Boston weather conditions."
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
k2.metric("Unique Alert IDs", f"{filtered['alert_id'].nunique():,}")
k3.metric("Routes Affected", f"{filtered['route_id'].nunique()}")
k4.metric(
    "Avg Temp on Alert Days",
    f"{filtered['avg_temperature_f'].mean():.1f} °F" if filtered["avg_temperature_f"].notna().any() else "N/A"
)

st.divider()

# ── Row 1: Alerts over time + by route ───────────────────────────────────────

row1_left, row1_right = st.columns([2, 1])

with row1_left:
    st.subheader("Alerts Over Time")
    weekly = (
        filtered.groupby(["week", "route_id"])
        .size()
        .reset_index(name="alert_count")
    )
    fig = px.line(
        weekly,
        x="week",
        y="alert_count",
        color="route_id",
        labels={"week": "Week", "alert_count": "Alerts", "route_id": "Route"},
        color_discrete_map={
            "Red": "#DA291C",
            "Blue": "#003DA5",
            "Orange": "#ED8B00",
            "Green-B": "#00843D",
            "Green-C": "#00843D",
            "Green-D": "#00843D",
            "Green-E": "#00843D",
        },
    )
    fig.update_layout(margin=dict(t=20, b=20), legend_title_text="Route")
    st.plotly_chart(fig, use_container_width=True)

with row1_right:
    st.subheader("Alerts by Route")
    by_route = filtered.groupby("route_id").size().reset_index(name="alert_count").sort_values("alert_count", ascending=True)
    fig2 = px.bar(
        by_route,
        x="alert_count",
        y="route_id",
        orientation="h",
        labels={"alert_count": "Alerts", "route_id": "Route"},
        color="route_id",
        color_discrete_map={
            "Red": "#DA291C",
            "Blue": "#003DA5",
            "Orange": "#ED8B00",
            "Green-B": "#00843D",
            "Green-C": "#00843D",
            "Green-D": "#00843D",
            "Green-E": "#00843D",
        },
    )
    fig2.update_layout(margin=dict(t=20, b=20), showlegend=False)
    st.plotly_chart(fig2, use_container_width=True)

# ── Row 2: Alert causes + weather correlation ─────────────────────────────────

row2_left, row2_right = st.columns(2)

with row2_left:
    st.subheader("Alert Causes")
    causes = (
        filtered.groupby("alert_cause")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .head(10)
    )
    fig3 = px.bar(
        causes,
        x="alert_cause",
        y="count",
        labels={"alert_cause": "Cause", "count": "Alerts"},
    )
    fig3.update_layout(margin=dict(t=20, b=20), xaxis_tickangle=-30)
    st.plotly_chart(fig3, use_container_width=True)

with row2_right:
    st.subheader("Alerts vs. Temperature")
    weather_df = (
        filtered.dropna(subset=["avg_temperature_f"])
        .groupby(["alert_start_date", "avg_temperature_f"])
        .size()
        .reset_index(name="alert_count")
    )
    if not weather_df.empty:
        fig4 = px.scatter(
            weather_df,
            x="avg_temperature_f",
            y="alert_count",
            trendline="ols",
            labels={"avg_temperature_f": "Avg Temperature (°F)", "alert_count": "Alerts"},
            opacity=0.6,
        )
        fig4.update_layout(margin=dict(t=20, b=20))
        st.plotly_chart(fig4, use_container_width=True)
    else:
        st.info("Weather data not yet joined — check back once more data has accumulated.")

# ── Row 3: Precipitation + wind ───────────────────────────────────────────────

row3_left, row3_right = st.columns(2)

with row3_left:
    st.subheader("Alerts vs. Precipitation")
    precip_df = (
        filtered.dropna(subset=["avg_precipitation_mm"])
        .groupby(["alert_start_date", "avg_precipitation_mm"])
        .size()
        .reset_index(name="alert_count")
    )
    if not precip_df.empty:
        fig5 = px.scatter(
            precip_df,
            x="avg_precipitation_mm",
            y="alert_count",
            trendline="ols",
            labels={"avg_precipitation_mm": "Avg Precipitation (mm)", "alert_count": "Alerts"},
            opacity=0.6,
        )
        fig5.update_layout(margin=dict(t=20, b=20))
        st.plotly_chart(fig5, use_container_width=True)
    else:
        st.info("Precipitation data not yet available.")

with row3_right:
    st.subheader("Alert Effects")
    effects = (
        filtered.groupby("alert_effect")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .head(10)
    )
    fig6 = px.pie(
        effects,
        names="alert_effect",
        values="count",
        hole=0.4,
    )
    fig6.update_layout(margin=dict(t=20, b=20))
    st.plotly_chart(fig6, use_container_width=True)

# ── Footer ────────────────────────────────────────────────────────────────────

st.divider()
st.caption(
    f"Data refreshed twice daily at 7am & 7pm ET · "
    f"{len(df):,} total records · "
    "Source: MBTA Alerts API + NWS Boston Logan Airport (KBOS)"
)
