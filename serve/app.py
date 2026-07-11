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
selected_lines = st.multiselect("Filter By Route", all_lines, default=all_lines)

selected_route_ids = [r for line in selected_lines for r in LINE_TO_ROUTES[line]]
filtered_alerts    = df_alerts[df_alerts["route_id"].isin(selected_route_ids)]

# 12-month window — applied to all charts (Past Alerts table shows full history)
year_start  = today - pd.DateOffset(months=12)
year_alerts = filtered_alerts[filtered_alerts["alert_start_date"] >= year_start]

# Ridership: most recent 12 months of available data (anchored to latest date, not today)
_max_ridership_date = df_ridership["service_date"].max() if not df_ridership.empty else today
_ridership_12mo_start = _max_ridership_date - pd.DateOffset(months=12)
filtered_ridership = df_ridership[
    df_ridership["route_name"].isin(selected_lines) &
    (df_ridership["service_date"] >= _ridership_12mo_start)
]

# Stable cause color order — computed once so both cause charts use matching colors
cause_order = sorted(filtered_alerts["alert_cause"].dropna().unique().tolist())

st.caption("Alerts & weather refresh 4× daily (midnight, 6AM, noon, 6PM ET) · Ridership & routes update quarterly · Alert charts: last 12 months · Past Alerts: full history")

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
st.divider()

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
    st.plotly_chart(fig, use_container_width=True)

with al_c2:
    st.subheader("Alerts By Month")
    monthly_df = year_alerts.copy()
    monthly_df["month"] = monthly_df["alert_start_date"].dt.to_period("M").dt.to_timestamp()
    monthly = monthly_df.groupby("month").size().reset_index(name="alert_count")
    fig = px.bar(
        monthly, x="month", y="alert_count",
        color_discrete_sequence=["#4e9af1"],
        labels={"month": "Month", "alert_count": "Alerts"},
    )
    fig.update_layout(**DARK_LAYOUT)
    fig.update_yaxes(tickformat="d", rangemode="tozero")
    fig.update_xaxes(
        range=[today - pd.DateOffset(months=12), today.replace(day=1) + pd.DateOffset(months=1) - pd.Timedelta(days=1)],
        dtick="M1", tickformat="%b %Y", tickangle=-30,
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# Cause share + Effect share side by side
cs_c1, cs_c2 = st.columns(2)
with cs_c1:
    st.subheader("Alert Cause Share")
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
    st.plotly_chart(fig, use_container_width=True)

with cs_c2:
    st.subheader("Alert Effect Share")
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
    st.plotly_chart(fig, use_container_width=True)

# Cause breakdown by route — normalized to % so routes with fewer alerts are still comparable
cr_c1, cr_c2 = st.columns(2)
with cr_c1:
    st.subheader("Alert Causes By Route")
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
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data.")

with cr_c2:
    st.subheader("Alert Effects By Route")
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
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data.")

st.divider()

# Cause → Effect heatmap
st.subheader("What Causes Lead to What Effects")
st.caption("Cell value = number of alerts with that cause/effect combination.")
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
    st.subheader("Daily Ridership vs Active Alerts")
    st.caption("Ridership updated quarterly with ~1–2 month delay.")

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
    st.subheader("Average Ridership By Day")
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
st.caption("Sources: MBTA Alerts API · NWS Weather API · MBTA ArcGIS Open Data")