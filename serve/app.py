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
</style>
""", unsafe_allow_html=True)

# ── Color maps ─────────────────────────────────────────────────────────────────

ROUTE_COLORS = {
    "Red":     "#DA291C",
    "Blue":    "#003DA5",
    "Orange":  "#ED8B00",
    "Green-B": "#005A28",
    "Green-C": "#00843D",
    "Green-D": "#4DBD74",
    "Green-E": "#93D6A8",
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
    return ROUTE_COLORS.get(route_id, "#00843D")

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
            alert_id,
            route_id,
            route_name,
            alert_start_date,
            alert_end_date,
            alert_duration_days,
            alert_header,
            alert_description,
            alert_cause,
            alert_effect,
            alert_severity
        FROM `{PROJECT_ID}.gold.rail_alerts`
        WHERE alert_start_date IS NOT NULL
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
            total_precipitation_mm,
            avg_wind_speed_mph,
            avg_humidity_percent
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
df_ridership["service_date"]  = pd.to_datetime(df_ridership["service_date"])

today       = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)
month_start = today.replace(day=1)

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown(
    "<h1 style='text-align:center; color:#ffffff;'>🚇 MBTA Reliability Analytics</h1>",
    unsafe_allow_html=True,
)

# ── Global line filter ───────────────────────────────────────────────────────

all_lines     = ["Red Line", "Orange Line", "Blue Line", "Green Line"]
selected_lines = st.multiselect("Filter by Line", all_lines, default=all_lines)

selected_route_ids = [r for line in selected_lines for r in LINE_TO_ROUTES[line]]
filtered_alerts    = df_alerts[df_alerts["route_id"].isin(selected_route_ids)]
filtered_ridership = df_ridership[df_ridership["route_name"].isin(selected_lines)]

# ── KPI row ───────────────────────────────────────────────────────────────────

active_alerts = filtered_alerts[
    filtered_alerts["alert_end_date"].isna() | (filtered_alerts["alert_end_date"] >= today)
]
month_alerts = filtered_alerts[filtered_alerts["alert_start_date"] >= month_start]

st.divider()
k1, k2, k3, k4 = st.columns(4)
k1.metric("Active Alerts",             f"{len(active_alerts):,}")
k2.metric("Routes Currently Impacted", f"{active_alerts['route_id'].nunique()}")
k3.metric("Alerts This Month",         f"{len(month_alerts):,}")
avg_dur = df_alerts["alert_duration_days"].mean()
k4.metric("Avg Alert Duration",        f"{avg_dur:.1f} days" if pd.notna(avg_dur) else "N/A")
st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# ALERTS SECTION
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("<h2 style='text-align:center'>🚨 Alerts</h2>", unsafe_allow_html=True)

# Active alerts table
st.subheader("Active Alerts")
active_filtered = filtered_alerts[
    filtered_alerts["alert_end_date"].isna() | (filtered_alerts["alert_end_date"] >= today)
]
if active_filtered.empty:
    st.info("No active alerts right now.")
else:
    display = active_filtered[[
        "route_id", "alert_effect", "alert_cause",
        "alert_start_date", "alert_end_date", "alert_duration_days",
        "alert_header", "alert_description",
    ]].rename(columns={
        "route_id": "Route", "alert_effect": "Effect", "alert_cause": "Cause",
        "alert_start_date": "Start", "alert_end_date": "End",
        "alert_duration_days": "Duration (days)",
        "alert_header": "Header", "alert_description": "Description",
    }).copy()
    display["Start"] = display["Start"].dt.date
    display["End"]   = display["End"].apply(lambda x: x.date() if pd.notna(x) else "Ongoing")
    st.dataframe(display, use_container_width=True, hide_index=True)

st.divider()

# Past Alerts — completed only (have a real end date in the past)
st.subheader("Past Alerts")

past_alerts = filtered_alerts[
    filtered_alerts["alert_end_date"].notna() &
    (filtered_alerts["alert_end_date"] < today)
]

hist_display = past_alerts[[
    "route_id", "alert_effect", "alert_cause",
    "alert_start_date", "alert_end_date", "alert_duration_days",
    "alert_header", "alert_description",
]].rename(columns={
    "route_id": "Route", "alert_effect": "Effect", "alert_cause": "Cause",
    "alert_start_date": "Start", "alert_end_date": "End",
    "alert_duration_days": "Duration (days)",
    "alert_header": "Header", "alert_description": "Description",
}).copy()
hist_display["Start"] = hist_display["Start"].dt.date
hist_display["End"]   = hist_display["End"].apply(lambda x: x.date() if pd.notna(x) else "Ongoing")

st.caption(f"{len(past_alerts):,} alerts")
st.dataframe(hist_display, use_container_width=True, hide_index=True, height=400)

st.divider()

# Alerts by route + by month
al_c1, al_c2 = st.columns(2)
with al_c1:
    st.subheader("Alerts By Route")
    route_counts = filtered_alerts.groupby("route_id").size().reset_index(name="alert_count")
    fig = px.bar(
        route_counts, x="route_id", y="alert_count",
        color="route_id", color_discrete_map=ROUTE_COLORS,
        labels={"route_id": "Route", "alert_count": "Alerts"},
    )
    fig.update_layout(**DARK_LAYOUT)
    fig.update_yaxes(tickformat="d", rangemode="tozero")
    st.plotly_chart(fig, use_container_width=True)

with al_c2:
    st.subheader("Alerts By Month")
    monthly_df = filtered_alerts.copy()
    monthly_df["month"] = monthly_df["alert_start_date"].dt.to_period("M").dt.to_timestamp()
    monthly = monthly_df.groupby(["month", "route_id"]).size().reset_index(name="alert_count")
    fig = px.bar(
        monthly, x="month", y="alert_count",
        color="route_id", barmode="stack",
        color_discrete_map=ROUTE_COLORS,
        labels={"month": "Month", "alert_count": "Alerts", "route_id": "Route"},
    )
    fig.update_layout(**DARK_LAYOUT)
    fig.update_yaxes(tickformat="d", rangemode="tozero")
    fig.update_xaxes(
        range=[today - pd.DateOffset(months=12), today + pd.DateOffset(months=1)],
        dtick="M1", tickformat="%b %Y", tickangle=-30,
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# Cause share + by cause
ca_c1, ca_c2 = st.columns(2)
with ca_c1:
    st.subheader("Alert Cause Share")
    causes = (
        filtered_alerts.groupby("alert_cause").size()
        .reset_index(name="count").sort_values("count", ascending=False).head(10)
    )
    fig = px.pie(
        causes, names="alert_cause", values="count", hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_traces(textfont_color="white")
    fig.update_layout(**{**DARK_LAYOUT, "showlegend": True})
    st.plotly_chart(fig, use_container_width=True)

with ca_c2:
    st.subheader("Alerts By Cause")
    cause_route = filtered_alerts.groupby(["alert_cause", "route_id"]).size().reset_index(name="count")
    if not cause_route.empty:
        fig = px.bar(
            cause_route, x="alert_cause", y="count",
            color="route_id", barmode="stack",
            color_discrete_map=ROUTE_COLORS,
            labels={"alert_cause": "Cause", "count": "Alerts", "route_id": "Route"},
        )
        fig.update_layout(**{**DARK_LAYOUT, "xaxis_tickangle": -30})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data.")

st.divider()

# Cause → Effect heatmap
st.subheader("What Causes Lead to What Effects")
st.caption("Cell value = number of alerts with that cause/effect combination.")
heat_df = (
    filtered_alerts
    .groupby(["alert_cause", "alert_effect"])
    .size()
    .reset_index(name="count")
)
if not heat_df.empty:
    heat_pivot = heat_df.pivot(index="alert_cause", columns="alert_effect", values="count").fillna(0)
    fig = px.imshow(
        heat_pivot,
        color_continuous_scale="Blues",
        text_auto=True,
        aspect="auto",
        labels={"x": "Effect", "y": "Cause", "color": "Alerts"},
    )
    fig.update_layout(
        **DARK_LAYOUT,
        coloraxis_colorbar=dict(title="Alerts", tickfont=dict(color="#ffffff")),
        xaxis_tickangle=-30,
    )
    st.plotly_chart(fig, use_container_width=True)
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

    # Ridership over time with alert count overlay
    st.subheader("Daily Ridership & Active Alerts")
    st.caption(
        "Bars show daily gated entries per line (left axis). "
        "Dotted lines show active alert count for that line (right axis). "
        "Ridership updated quarterly with ~1–2 month delay."
    )

    fig = go.Figure()
    for line in selected_lines:
        line_data = filtered_ridership[filtered_ridership["route_name"] == line].sort_values("service_date")
        color = LINE_COLORS.get(line, "#888888")
        fig.add_trace(go.Bar(
            name=line,
            x=line_data["service_date"],
            y=line_data["ridership"],
            marker_color=color,
            opacity=0.8,
            yaxis="y1",
        ))
        fig.add_trace(go.Scatter(
            name=f"{line} Alerts",
            x=line_data["service_date"],
            y=line_data["line_alert_count"],
            mode="lines",
            line=dict(color=color, dash="dot", width=2),
            yaxis="y2",
        ))

    fig.update_layout(**DARK_LAYOUT)
    fig.update_layout(
        barmode="group",
        yaxis=dict(title="Daily Ridership", gridcolor="#30363d", rangemode="tozero"),
        yaxis2=dict(
            title="Active Alerts", overlaying="y", side="right",
            rangemode="tozero", gridcolor="rgba(0,0,0,0)",
            dtick=1, tickformat="d",
        ),
        legend=dict(bgcolor="#161b22", bordercolor="#30363d", borderwidth=1),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Day of week ridership
    st.subheader("Average Ridership By Day Of Week")
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
        labels={"day_of_week": "Day", "ridership": "Avg Ridership", "route_name": "Line"},
    )
    fig.update_layout(**DARK_LAYOUT)
    st.plotly_chart(fig, use_container_width=True)

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
            st.plotly_chart(fig, use_container_width=True)
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
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Precipitation data not yet available.")

# ── Footer ────────────────────────────────────────────────────────────────────

st.divider()
st.caption(
    f"Alerts refreshed twice daily (7 AM & 7 PM EST) · "
    f"Weather refreshed 4x daily · "
    f"Ridership updated quarterly from MBTA open data. "
    f"{len(df_alerts):,} alerts · {len(df_ridership):,} ridership records. "
    "Sources: MBTA Alerts API · NWS Weather API · MBTA ArcGIS Open Data"
)
