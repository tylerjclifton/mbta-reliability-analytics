"""
Dashboard — MBTA Reliability & Ridership, served with Streamlit

Reads:      gold.rail_incidents, gold.rail_incident_stations,
            gold.rail_incident_periods, gold.rail_stations, gold.rail_shapes,
            gold.rail_ridership, gold.rail_delay_estimates,
            gold.transit_ridership, gold.commuter_rail_boardings,
            gold.ferry_performance, gold.rail_trip_times,
            gold.commuter_rail_reliability, gold.transit_rider_satisfaction
            (cached for 15 minutes)
Deployed:   Cloud Run service `serve` (infra/cloud-run-services.tf), public at
            tylerclifton.com

Layout:
  1. Header + line filter
  2. Service status     — KPIs, incidents happening now, planned work coming up
  3. Stations affected  — map of stations hit now or by planned work,
                          most-affected stations
  4. Incident patterns  — when, where, why, and how long, and how far the
                          MBTA's posted end times miss (trailing 12 months)
  5. Disruption by year — delays by length and out-of-service hours, each
                          full year of alert history
  6. Delays riders feel — extra minutes per trip on the Red, Orange, and Blue
                          Lines, and what riders tell the MBTA's survey, each
                          month from 2022
  7. Subway ridership   — per-line tiles (latest month), ridership by month
                          (2 years or all history) or by day (any run of
                          months), days that moved ridership, ridership by
                          alert effect, day of week
  8. Weather            — rain, snow, and temperature vs. typical ridership
  9. Every mode         — every mode's riders against 2019 (tiles, by month,
                          weekdays vs weekends), ferry riders by route,
                          commuter rail by day of the week and trains late by
                          line
  10. Footer            — sources, cadence, method notes

Sections 2–8 are the subway in depth: its incidents, from right now to the
long run (2–5), what riders felt of them (6), and its riders and what moves
them (7–8). Section 9 steps back to every mode: riders, and punctuality
where the MBTA publishes it for every trip (commuter rail, ferry).

Time windows: every section covers the trailing 12 months, stated in its
subtitle (every mode: each source's last 12 published months). Six
exceptions, also labeled: delays riders feel runs month by month from 2022,
when the MBTA's trip times begin; the ridership tiles show the latest
published month (each tile names it) against the same month a year earlier
and in 2019; monthly ridership shows the last 2 years (to compare each month
with a year earlier) or, switched, all history or any months day by day; days
that moved ridership are
chosen days from all history; disruption by year uses every full year of
alert history; and weather uses all available days (snowstorms are too rare
for a single winter).

Statistics: volumes are averages (entries per day, which add up); "typical"
values are medians (durations, and every baseline a comparison is made
against, so one shutdown or months-long incident can't skew them).
Comparisons are like-for-like: same line, same month, weekday-adjusted, with
federal holidays left out.

Copy and numbers: section intros are one sentence or two; card subtitles are
fragments joined by " · ", with no closing period; method detail lives in the
footer. Counts take thousands separators, and K from 10,000 up (an axis uses K
throughout once its top tick reaches that). Shares are whole percents, changes
take one decimal. Partial periods are dimmed.

Charts: each goes through style() (transparent surface, hairline grid, muted
axes) and show() (read-only, so no chart traps page scrolling); the station map
is the one figure that zooms. Color follows the entity: each line keeps its
official color everywhere, in LINE_COLORS order, legends included; a single
series uses ACCENT, and heatmaps use SEQUENTIAL. Text stays in the ink tokens,
never a series color, and line-colored marks carry a direct label. Bars have
rounded ends (cornerradius 4), and value labels sit LABEL_GAP from their marks.

Counting unit is the incident (gold.rail_incidents): one real-world event the
MBTA may have posted as several alerts.

Two ridership comparisons, each detailed where it's computed:
  % vs typical    (weather) a day's entries vs the median for the same line,
                  weekday, and month; see load_ridership()
  % vs calm days  (alert effects) a day's entries vs the line's calm days (no
                  incident but a station closure) in the same month, adjusted
                  for the day of the week; see helpers.pct_vs_calm()
"""

# Import standard libraries
import os

# Import third party libraries
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from google.cloud import bigquery
from pandas.tseries.holiday import USFederalHolidayCalendar

# Import dashboard helpers
from helpers import (
    TIMEZONE,
    day_vs_nearby,
    decode_polyline,
    effect_vs_calm,
    esc,
    fmt_count,
    fmt_count_change,
    fmt_day,
    fmt_duration,
    fmt_minutes,
    fmt_pct,
    freshness,
    hours_by_year,
    in_force,
    one_row_per_incident,
    pct_vs_calm,
    riders_per_day_by_mode,
    run_end_labels,
    spread_labels,
    strip_route_prefix,
)

# ══════════════════════════════════════════════════════════════════════════════
# Design tokens
# ══════════════════════════════════════════════════════════════════════════════

# Surfaces and ink (dark theme; page background is set
# in .streamlit/config.toml).
PAGE   = '#0b0d10'   # page background
CARD   = '#13161b'   # card surface
BORDER = 'rgba(255,255,255,0.08)'
INK    = '#f0efec'   # primary text
INK_2  = '#b4b6bd'   # secondary text
MUTED  = '#80838c'   # axis labels, captions
GRID   = '#22252c'   # hairline gridlines
AXIS   = '#3a3e47'   # baselines

# Neutral accent for single-series charts — deliberately not a line color, so
# it never reads as "Blue Line" or "Green Line".
ACCENT = '#9085e9'

# One-hue sequential ramp (dark → lighter on the dark surface) for heatmaps;
# capped so white cell labels stay readable on the brightest cell.
SEQUENTIAL = [[0.0, '#1c1a2e'], [1.0, '#7366d6']]

FONT = "Inter, system-ui, -apple-system, 'Segoe UI', sans-serif"

# Official MBTA line colors — the identity of every line-level visual. Official
# Blue is low-contrast on the dark surface, so line-colored marks always carry
# a direct text label as well.
LINE_COLORS = {
    'Red Line':    '#DA291C',
    'Orange Line': '#ED8B00',
    'Blue Line':   '#003DA5',
    'Green Line':  '#00843D',
}
LINES = list(LINE_COLORS)

# Every mode, largest first, for the "Every mode" section: the MBTA's
# own mode colors where it has one (bus yellow, commuter rail purple,
# lightened to read on the dark surface, ferry teal), Green for the Green Line
# and Mattapan, a neutral for the three heavy rail lines together. Each is
# named on the chart too.
MODE_COLORS = {
    'Red, Orange, Blue': '#c4c7ce',
    'Bus, Silver Line':  '#FFC72C',
    'Green, Mattapan':   '#00843D',
    'Commuter Rail':     '#b05aa4',
    'Ferry':             '#008EAA',
    'The RIDE':          '#9085e9',
}
MODES = list(MODE_COLORS)

WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

# Space between a mark and its value label (an em space), so
# labels never touch bars or dots.
LABEL_GAP = '\u2003'

# Thickness of a ranked chart's bars, in pixels.
BAR_PX = 22

# Who built this, linked from the header and footer.
AUTHOR = 'Tyler Clifton'
GITHUB_URL = 'https://github.com/tylerjclifton'
REPO_URL = f'{GITHUB_URL}/mbta-reliability-analytics'

# Stations the map always names, to orient the reader: each line's ends and the
# main hubs. Value = where the name sits relative to its dot.
MAP_LABELS = {
    'Alewife': 'middle left', 'Medford/Tufts': 'top center', 'Union Square': 'middle left',
    'Oak Grove': 'top center', 'Wonderland': 'middle right', 'Riverside': 'middle left',
    'Boston College': 'top left', 'Cleveland Circle': 'bottom center', 'Heath Street': 'bottom left',
    'Forest Hills': 'bottom center', 'Ashmont': 'middle left', 'Braintree': 'bottom center',
    'Harvard': 'top left', 'Kenmore': 'top left', 'Park Street': 'middle left', 'North Station': 'top right',
    'South Station': 'middle right', 'JFK/UMass': 'middle right',
}

# Charts are read-only: no toolbar, zoom, or pan (they
# fight page scrolling on mobile).
CHART_CONFIG = {'displayModeBar': False, 'scrollZoom': False, 'doubleClick': False}

# The station map zooms with +/−/reset buttons and pans by dragging; the scroll
# wheel still scrolls the page, so the map never traps it.
MAP_CONFIG = {'displayModeBar': True, 'displaylogo': False,
              'modeBarButtons': [['zoomInMap', 'zoomOutMap', 'resetViewMap']],
              'scrollZoom': False, 'doubleClick': False}

# ══════════════════════════════════════════════════════════════════════════════
# Page setup and global styles
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(page_title='MBTA Reliability & Ridership', page_icon='🚇', layout='wide')

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
/* Signature stripe above the title: one short bar per line, in its official color */
.hero .lines {{ display: flex; gap: 4px; margin-bottom: 1rem; }}
.hero .lines span {{ width: 28px; height: 4px; border-radius: 2px; }}
.hero p  {{ color: {INK_2}; font-size: 1.05rem; margin: 0 0 1rem; max-width: 54rem; }}
.status  {{ display: inline-flex; flex-wrap: wrap; gap: 0.35rem 1rem; color: {MUTED};
            font-size: 0.8rem; margin-bottom: 1.25rem; }}
.status a, .footer a {{ color: {INK_2}; text-decoration: underline; text-underline-offset: 2px; }}
/* Alerts status dot, colored by freshness() — late and stale also say so in text */
.status .dot::before {{ content: ""; display: inline-block; width: 7px; height: 7px;
            border-radius: 50%; margin-right: 0.4rem; vertical-align: 1px; }}
.status .fresh::before {{ background: #0ca30c; }}
.status .late::before  {{ background: #e5a50a; }}
.status .stale::before {{ background: #e5484d; }}

/* Section headers */
.section {{ margin: 3.25rem 0 1rem; }}
.section h2 {{ font-size: 1.5rem; font-weight: 650; letter-spacing: -0.01em; margin: 0; padding: 0; color: {INK}; }}
.section p  {{ color: {INK_2}; font-size: 0.92rem; margin: 0.35rem 0 0; max-width: 52rem; }}

/* Cards: every st.container(key="card_<name>") */
div[class*="st-key-card_"] {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 14px;
            padding: 1.15rem 1.25rem 0.75rem; }}
.card-title {{ font-size: 1rem; font-weight: 600; color: {INK}; margin: 0; }}
.card-sub   {{ font-size: 0.82rem; color: {MUTED}; margin: 0.15rem 0 0.5rem; }}

/* Cards side by side share one height, so every row has one bottom edge */
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] {{ height: 100%; }}
[data-testid="stColumn"] [data-testid="stLayoutWrapper"]:has(> div[class*="st-key-card_"]) {{ flex: 1 1 auto; }}

/* Toggles and filters: the selected option is the strongest thing in the group */
button[data-variant="segmented_control"][data-selected="true"] p,
button[data-variant="pills"][data-selected="true"] p {{ color: {INK}; font-weight: 600; }}
button[data-variant="segmented_control"]:not([data-selected="true"]) p,
button[data-variant="pills"]:not([data-selected="true"]) p {{ color: {MUTED}; }}

/* KPI tiles. Streamlit pulls every markdown block up 1rem, to absorb a
   closing paragraph's margin; a tile row has none, so it gives the 1rem back
   rather than hang over what follows. */
.kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 1rem;
         margin-bottom: 1rem; }}
.kpi  {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 14px; padding: 1rem 1.1rem;
         position: relative; overflow: hidden; }}
.kpi .stripe {{ position: absolute; left: 0; top: 0; bottom: 0; width: 4px; }}
.kpi .label  {{ color: {MUTED}; font-size: 0.8rem; font-weight: 500; }}
.kpi .value  {{ color: {INK}; font-size: 2rem; font-weight: 650; letter-spacing: -0.02em;
               line-height: 1.2; margin-top: 0.2rem; }}
.kpi .sub    {{ color: {INK_2}; font-size: 0.8rem; margin-top: 0.15rem; }}
/* Six tiles as two rows of three, not five and one */
.kpis.thirds {{ grid-template-columns: repeat(3, 1fr); }}
/* Inside a card, tiles sit flat on it, each under a hairline, not boxes in a box */
div[class*="st-key-card_"] .kpi {{ background: none; border: none; border-top: 1px solid {BORDER};
            border-radius: 0; padding: 0.75rem 0 0; }}
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

/* Station map: the basemap credit moves from the map's corner (where it covers
   stations) to a line under the map — still shown, as OpenStreetMap and CARTO
   require */
.st-key-card_station_map .maplibregl-ctrl-attrib {{ display: none; }}
.map-credit {{ color: {MUTED}; font-size: 0.72rem; text-align: right; margin: -0.75rem 0 0; padding-bottom: 0.4rem; }}
.map-credit a {{ color: {MUTED}; }}

/* First-load message while the data queries run */
.loading {{ color: {MUTED}; font-size: 0.95rem; }}

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

/* Phones: tighter gutters and type. Side-by-side cards stack on a phone, and
   the column gap (2rem) would become the space between them; within a section
   every gap is 1rem, so stacked cards match the space between rows. */
@media (max-width: 640px) {{
  .block-container {{ padding: 1.5rem 1rem 3rem; }}
  [data-testid="stHorizontalBlock"] {{ row-gap: 1rem !important; }}
  .hero h1 {{ font-size: 1.9rem; }}
  .section {{ margin-top: 2.5rem; }}
  .kpis, .kpis.thirds {{ grid-template-columns: repeat(2, 1fr); }}
  .kpi {{ padding: 0.85rem 0.9rem; }}
  .kpi .value {{ font-size: 1.5rem; }}
  .kpi .label, .kpi .sub {{ font-size: 0.74rem; }}
}}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# Layout helpers
# ══════════════════════════════════════════════════════════════════════════════

def section(title, subtitle=None):
    """Section heading with an optional one-line explanation."""
    sub = f'<p>{subtitle}</p>' if subtitle else ''
    st.markdown(f'<div class="section"><h2>{title}</h2>{sub}</div>', unsafe_allow_html=True)


def card_title(title, subtitle=None):
    """Title (and optional subtitle) at the top of a card."""
    sub = f'<div class="card-sub">{subtitle}</div>' if subtitle else '<div class="card-sub"></div>'
    st.markdown(f'<div class="card-title">{title}</div>{sub}', unsafe_allow_html=True)


def kpi_tiles(tiles, layout=''):
    """
    Row of KPI tiles. Each tile: dict(label, value, sub=None, color=None).
    `color` draws a left stripe (used for line-specific tiles); `layout`
    "thirds" sets three columns, for six tiles.
    """
    cells = []
    for t in tiles:
        stripe = f'<div class="stripe" style="background:{t["color"]}"></div>' if t.get('color') else ''
        sub = f'<div class="sub">{t["sub"]}</div>' if t.get('sub') else ''
        cells.append(f'<div class="kpi">{stripe}<div class="label">{t["label"]}</div>'
                     f'<div class="value">{t["value"]}</div>{sub}</div>')
    st.markdown(f'<div class="kpis {layout}">{"".join(cells)}</div>', unsafe_allow_html=True)


def incident_items(df, when):
    """HTML list of incidents; `when(row)` returns the timing line."""
    items = []
    for _, row in df.iterrows():
        color = LINE_COLORS.get(row['line_name'], MUTED)
        items.append(
            f'<div class="inc"><div class="bar" style="background:{color}"></div><div>'
            f'<div class="top"><span class="route">{esc(row["route_name"])}</span>'
            f'<span class="badge">{esc(row["incident_effect"])}</span>'
            f'<span class="cause">{esc(row["incident_cause"])}</span></div>'
            f'<div class="text">{esc(strip_route_prefix(row["incident_header"]))}</div>'
            f'<div class="meta">{when(row)}</div></div></div>'
        )
    return ''.join(items)


def incident_list(df, when, empty_text, limit=5):
    """
    First `limit` incidents inline; the rest behind a "Show more" expander.
    """
    if df.empty:
        st.markdown(f'<div class="empty">{empty_text}</div>', unsafe_allow_html=True)
        return
    st.markdown(incident_items(df.head(limit), when), unsafe_allow_html=True)
    if len(df) > limit:
        with st.expander(f'Show {len(df) - limit} more'):
            st.markdown(incident_items(df.iloc[limit:], when), unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# Chart helpers — one look for every chart
# ══════════════════════════════════════════════════════════════════════════════

def style(fig, height=300, legend=False):
    """
    Apply the shared chart style: transparent surface,
    hairline grid, muted axes.
    """
    # automargin grows the margin to fit long tick labels ("Medical Emergency")
    # instead of clipping them; standoff keeps labels off the axis line.
    axis = dict(gridcolor=GRID, linecolor=AXIS, zeroline=False, fixedrange=True, automargin=True,
                tickfont=dict(color=MUTED, size=11), title=None, ticks='')
    fig.update_layout(
        height=height,
        margin=dict(l=4, r=12, t=8, b=4),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family=FONT, color=INK_2, size=12),
        showlegend=legend,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0, font=dict(color=INK_2, size=11),
                    bgcolor='rgba(0,0,0,0)'),
        hoverlabel=dict(bgcolor='#1c2027', bordercolor=BORDER, font=dict(family=FONT, color=INK, size=12)),
        bargap=0.35,
        xaxis=dict(axis, ticklabelstandoff=6),
        yaxis=dict(axis, ticklabelstandoff=10),
    )
    return fig


def count_axis(fig, top, axis='y'):
    """
    Label a count axis like the KPI tiles (126K, 3.2M) with ~4 round ticks from
    0 to `top`. One unit per axis: never 5,000 beside 10K. Returns whether the
    axis is in K, so value labels beside it can match (fmt_count's `thousands`).
    """
    raw = max(top, 1) / 4
    magnitude = 10 ** np.floor(np.log10(raw))
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)
    ticks = np.arange(0, top + step, step)
    in_thousands = 10_000 <= ticks[-1] < 1_000_000
    labels = [f'{t / 1_000:g}K' if in_thousands and t else fmt_count(t) for t in ticks]
    getattr(fig, f'update_{axis}axes')(tickvals=ticks, ticktext=labels, range=[0, ticks[-1] * 1.04])
    return in_thousands


def show(fig, config=CHART_CONFIG):
    """
    Render a Plotly figure full-width with the shared
    chart config (no zoom/pan toolbar).
    """
    st.plotly_chart(fig, config=config, width='stretch')


def label_line_ends(fig, ends, top, colors=LINE_COLORS):
    """
    Mark where each line chart series ends: a dot in the series' color and a
    text label beside it, spaced so labels never overlap (identity is never
    color alone). `ends` is a list of (series, x, y, text); `top` is the
    y-axis maximum, which sets the spacing; `colors` maps series to colors.
    """
    label_y = spread_labels([y for _, _, y, _ in ends], min_gap=top * 0.06)
    for (line, x, y, text), at in zip(ends, label_y, strict=True):
        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode='markers',
            marker=dict(color=colors[line], size=9, line=dict(color=CARD, width=2)),
            showlegend=False, hoverinfo='skip', cliponaxis=False,
        ))
        fig.add_annotation(text=text, x=x, y=at, xanchor='left', xshift=10, showarrow=False,
                           font=dict(color=INK_2, size=11))


def ranked_bars(labels, values, text, hover, colors=ACCENT, height=None):
    """
    Horizontal bars, largest on top, value label at each bar's tip. Bars are
    BAR_PX thick however tall the chart is, so ranked charts match across cards.
    """
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation='h',
        marker=dict(color=colors, cornerradius=4),
        text=[LABEL_GAP + t for t in text], textposition='outside', constraintext='none',
        textfont=dict(color=INK_2, size=11), cliponaxis=False,
        hovertext=hover, hoverinfo='text',
    ))
    height = height or max(180, 34 * len(labels) + 30)
    style(fig, height=height)
    fig.update_layout(bargap=max(0.35, 1 - BAR_PX / ((height - 30) / max(len(labels), 1))))
    fig.update_yaxes(autorange='reversed', gridcolor='rgba(0,0,0,0)', tickfont=dict(color=INK_2, size=12))
    # Value labels render into a fixed right margin (not a share of the axis),
    # so the longest label fits at every screen width.
    fig.update_layout(margin=dict(l=4, r=84, t=8, b=4))
    fig.update_xaxes(visible=False, range=[0, max(values) * 1.02 if len(values) else 1])
    return fig


def share_bars(counts, colors=ACCENT, height=None):
    """
    Ranked incident counts (a Series: label → count), each
    labeled with its count and share.
    """
    share = counts / max(counts.sum(), 1) * 100
    return ranked_bars(
        labels=list(counts.index), values=list(counts.values),
        text=[f'{n:,.0f}  ·  {s:.0f}%' for n, s in zip(counts.values, share.values, strict=True)],
        hover=[f'{label}: {n:,.0f} incidents ({s:.0f}%)'
               for label, n, s in zip(counts.index, counts.values, share.values, strict=True)],
        colors=colors, height=height,
    )


def band_bars(df, baseline, y_range, height=260):
    """
    Weather-band bars: each band vs the `baseline` band (drawn at zero), signed
    label on each bar. Expects columns band, pct, days. `y_range` is passed in
    so charts side by side can share one scale.
    """
    fig = go.Figure(go.Bar(
        x=df['band'].astype(str), y=df['pct'],
        marker=dict(color=ACCENT, cornerradius=4),
        # The baseline band is zero by definition; label it as such. Any other
        # band can land on exactly zero too (medians often do), and shows it.
        text=['baseline' if band == baseline else fmt_pct(pct)
              for band, pct in zip(df['band'], df['pct'], strict=True)],
        textposition='outside', constraintext='none', cliponaxis=False, textfont=dict(color=INK_2, size=11),
        hovertext=[f'{band}<br>{fmt_pct(pct)} vs normal days · {days} days'
                   for band, pct, days in zip(df['band'], df['pct'], df['days'], strict=True)],
        hoverinfo='text',
    ))
    style(fig, height=height)
    fig.update_yaxes(range=y_range, ticksuffix='%', zeroline=True, zerolinecolor=AXIS, zerolinewidth=1)
    # Ranges ("−10 to −5°") break after "to", so
    # neighbors don't touch at phone width.
    bands = df['band'].astype(str)
    fig.update_xaxes(tickfont=dict(color=INK_2, size=11), tickvals=bands,
                     ticktext=[band.replace(' to ', ' to<br>') for band in bands])
    return fig

# ══════════════════════════════════════════════════════════════════════════════
# Data
# ══════════════════════════════════════════════════════════════════════════════

PROJECT_ID = os.getenv('GCP_PROJECT_ID', 'mbta-reliability-analytics')
# Dataset to read; point at dev_gold to preview a local dbt build.
GOLD_DATASET = os.getenv('BQ_DATASET_ID', 'gold')
# Fail any single query that would bill more than 1 GiB (~$0.006), the
# dashboard's cost guardrail (infra/quotas.tf says why it isn't a
# project-wide daily cap). Each gold table was ~0.2 MiB in 2026-10, so
# this leaves decades of headroom.
MAX_BYTES_BILLED = 1024**3


@st.cache_resource
def get_client():
    """
    BigQuery client shared by every query; each query is
    capped at MAX_BYTES_BILLED.
    """
    return bigquery.Client(
        project=PROJECT_ID,
        default_query_job_config=bigquery.QueryJobConfig(maximum_bytes_billed=MAX_BYTES_BILLED),
    )


# Cache 15 minutes: gold's alert tables rebuild hourly, so the page's alerts
# are at most ~75 minutes behind.
@st.cache_data(ttl=900, show_spinner=False)
def load_incidents():
    """
    gold.rail_incidents, one row per incident × route;
    timestamps as UTC datetimes.
    """
    df = get_client().query(f"""
        SELECT
            incident_id, route_id, route_name, line_name,
            incident_cause, incident_effect, incident_header,
            incident_start_at, incident_end_at, incident_duration_minutes,
            alert_count, is_in_feed, ingested_at
        FROM `{PROJECT_ID}.{GOLD_DATASET}.rail_incidents`
    """).to_dataframe()
    for col in ['incident_start_at', 'incident_end_at', 'ingested_at']:
        df[col] = pd.to_datetime(df[col], utc=True)
    return df


@st.cache_data(ttl=900, show_spinner=False)
def load_incident_stations():
    """
    gold.rail_incident_stations, one row per incident ×
    route × station, for the map.
    """
    df = get_client().query(f"""
        SELECT
            incident_id, station_id, route_name, line_name, station_name,
            station_latitude, station_longitude, is_both_directions, direction_destination,
            incident_effect, incident_start_at, incident_end_at
        FROM `{PROJECT_ID}.{GOLD_DATASET}.rail_incident_stations`
    """).to_dataframe()
    for col in ['incident_start_at', 'incident_end_at']:
        df[col] = pd.to_datetime(df[col], utc=True)
    return df


@st.cache_data(ttl=900, show_spinner=False)
def load_incident_periods():
    """
    gold.rail_incident_periods, one row per incident × route × alert period:
    when each incident was in force.
    """
    df = get_client().query(f"""
        SELECT incident_id, route_name, line_name, incident_effect, period_start_at, period_end_at
        FROM `{PROJECT_ID}.{GOLD_DATASET}.rail_incident_periods`
    """).to_dataframe()
    for col in ['period_start_at', 'period_end_at']:
        df[col] = pd.to_datetime(df[col], utc=True)
    return df


@st.cache_data(ttl=900, show_spinner=False)
def load_stations():
    """gold.rail_stations, one row per station × line: the map's backdrop."""
    return get_client().query(f"""
        SELECT station_id, line_name, station_name, station_latitude, station_longitude
        FROM `{PROJECT_ID}.{GOLD_DATASET}.rail_stations`
    """).to_dataframe()


@st.cache_data(ttl=900, show_spinner=False)
def load_shapes():
    """
    gold.rail_shapes, one row per canonical shape ×
    route, decoded: the map's lines.
    """
    df = get_client().query(f"""
        SELECT line_name, shape_id, shape_polyline
        FROM `{PROJECT_ID}.{GOLD_DATASET}.rail_shapes`
    """).to_dataframe()
    return df.assign(points=df['shape_polyline'].map(decode_polyline))


@st.cache_data(ttl=900, show_spinner=False)
def load_delay_estimates():
    """
    gold.rail_delay_estimates, one row per subway delay × line: the end the MBTA
    first posted, against the all-clear.
    """
    df = get_client().query(f"""
        SELECT alert_id, line_name, alert_created_at, estimated_minutes, actual_minutes
        FROM `{PROJECT_ID}.{GOLD_DATASET}.rail_delay_estimates`
    """).to_dataframe()
    df['alert_created_at'] = pd.to_datetime(df['alert_created_at'], utc=True)
    return df


@st.cache_data(ttl=900, show_spinner=False)
def load_ridership():
    """
    gold.rail_ridership, one row per service date × line, plus each day's
    "% vs typical" and whether it's a federal holiday. Fare-free days are left
    out: the gates stood open, so their entries aren't ridership (the Blue
    Line, Jul 5 – Aug 4, 2024, counted 4–80 a day).
    """
    df = get_client().query(f"""
        SELECT
            service_date, line_name, gated_entries, active_incident_count,
            most_severe_effect, is_calm_day, avg_temperature_f, precipitation_in, snowfall_in
        FROM `{PROJECT_ID}.{GOLD_DATASET}.rail_ridership`
        WHERE NOT is_fare_free
    """).to_dataframe()
    df['service_date'] = pd.to_datetime(df['service_date'])

    # "% vs typical": entries relative to the median for the same line, weekday,
    # and month — strips out line size, weekday pattern, and seasonality.
    df['weekday'] = df['service_date'].dt.day_of_week
    df['month'] = df['service_date'].dt.to_period('M')
    typical = df.groupby(['line_name', 'weekday', 'month'])['gated_entries'].transform('median')
    df['pct_vs_typical'] = (df['gated_entries'] / typical - 1) * 100

    # Federal holidays are not typical for their weekday; flag them so "% vs
    # typical" comparisons skip them.
    holidays = USFederalHolidayCalendar().holidays(df['service_date'].min(), df['service_date'].max())
    df['is_holiday'] = df['service_date'].isin(holidays)
    return df


@st.cache_data(ttl=900, show_spinner=False)
def load_transit_ridership():
    """
    gold.transit_ridership, one row per month × day type × service: the MBTA's
    monthly boardings on every mode.
    """
    df = get_client().query(f"""
        SELECT month_start, day_type, day_count, mode, service, riders_total
        FROM `{PROJECT_ID}.{GOLD_DATASET}.transit_ridership`
    """).to_dataframe()
    df['month_start'] = pd.to_datetime(df['month_start'])
    return df


@st.cache_data(ttl=900, show_spinner=False)
def load_commuter_rail_boardings():
    """gold.commuter_rail_boardings, one row per service date × line."""
    df = get_client().query(f"""
        SELECT service_date, line_name, estimated_boardings
        FROM `{PROJECT_ID}.{GOLD_DATASET}.commuter_rail_boardings`
    """).to_dataframe()
    df['service_date'] = pd.to_datetime(df['service_date'])
    return df


@st.cache_data(ttl=900, show_spinner=False)
def load_ferry_performance():
    """gold.ferry_performance, one row per month × ferry route."""
    df = get_client().query(f"""
        SELECT month_start, route_name, riders, service_days, measured_legs, on_time_legs
        FROM `{PROJECT_ID}.{GOLD_DATASET}.ferry_performance`
    """).to_dataframe()
    df['month_start'] = pd.to_datetime(df['month_start'])
    return df


@st.cache_data(ttl=900, show_spinner=False)
def load_trip_times():
    """gold.rail_trip_times summed per month × line, the grain the dashboard shows."""
    df = get_client().query(f"""
        SELECT
            DATE_TRUNC(service_date, MONTH) AS month_start,
            line_name,
            MAX(service_date) AS through_date,
            SUM(riders_estimated) AS riders,
            SUM(trip_minutes - baseline_trip_minutes) AS extra_minutes,
            SUM(riders_within_5_minutes) AS riders_within_5
        FROM `{PROJECT_ID}.{GOLD_DATASET}.rail_trip_times`
        GROUP BY month_start, line_name
    """).to_dataframe()
    df[['month_start', 'through_date']] = df[['month_start', 'through_date']].apply(pd.to_datetime)
    return df


@st.cache_data(ttl=900, show_spinner=False)
def load_commuter_rail_reliability():
    """gold.commuter_rail_reliability summed per day × line (peak and off-peak together)."""
    df = get_client().query(f"""
        SELECT
            service_date,
            line_name,
            SUM(trains_measured) AS trains_measured,
            SUM(trains_on_time) AS trains_on_time,
            SUM(trains_canceled) AS trains_canceled
        FROM `{PROJECT_ID}.{GOLD_DATASET}.commuter_rail_reliability`
        GROUP BY service_date, line_name
    """).to_dataframe()
    df['service_date'] = pd.to_datetime(df['service_date'])
    return df


@st.cache_data(ttl=900, show_spinner=False)
def load_rider_satisfaction():
    """gold.transit_rider_satisfaction, one row per survey × question."""
    df = get_client().query(f"""
        SELECT survey_month, question_label, respondents, positive_share
        FROM `{PROJECT_ID}.{GOLD_DATASET}.transit_rider_satisfaction`
    """).to_dataframe()
    df['survey_month'] = pd.to_datetime(df['survey_month'])
    return df


# A visitor's first load waits several seconds on the BigQuery queries with
# nothing on screen, which reads as a broken page; say it's loading until the
# dashboard replaces it. Later reruns (line filter clicks)
# keep the previous page visible instead, so the message only shows once.
loading = st.empty()
if 'loaded' not in st.session_state:
    loading.markdown('<div class="loading">Loading the latest MBTA data…</div>', unsafe_allow_html=True)

incidents_all = load_incidents()
incident_stations_all = load_incident_stations()
incident_periods_all = load_incident_periods()
stations_all = load_stations()
shapes_all = load_shapes()
delay_estimates_all = load_delay_estimates()
ridership_all = load_ridership()
transit_all = load_transit_ridership()
commuter_rail_all = load_commuter_rail_boardings()
ferry_all = load_ferry_performance()
trip_times_all = load_trip_times()
commuter_rail_reliability_all = load_commuter_rail_reliability()
satisfaction_all = load_rider_satisfaction()
loading.empty()
st.session_state['loaded'] = True

now = pd.Timestamp.now(tz='UTC')

if incidents_all.empty and ridership_all.empty:
    st.warning('No data available yet.')
    st.stop()

# Incident history begins with the earliest incident: the MBTA's LAMP archive
# supplies alerts from before the project's own capture (decision 0016).
tracking_start = incidents_all['incident_start_at'].min()

# Incident history only counts from when coverage became continuous. The
# subway never goes two weeks without an incident, so a gap that long means
# alerts weren't being captured (the project's own pipeline missed June 8 –
# July 1, 2026, a gap LAMP now fills). Coverage starts at the first incident
# after the last such gap, measured from the start of tracking and over
# incidents that have already begun (gaps between future planned work don't
# count). Before it, an empty day would read as a quiet day when it's really no
# data.
_starts = incidents_all.loc[incidents_all['incident_start_at'].between(tracking_start, now), 'incident_start_at']
_starts = pd.concat([pd.Series([tracking_start]), _starts]).sort_values().reset_index(drop=True)
_after_gap = _starts[_starts.diff() > pd.Timedelta(days=14)]
coverage_start = _after_gap.iloc[-1] if len(_after_gap) else tracking_start

# ══════════════════════════════════════════════════════════════════════════════
# 1. Header + line filter
# ══════════════════════════════════════════════════════════════════════════════

alerts_updated = incidents_all['ingested_at'].max()
ridership_through = ridership_all['service_date'].max()

# Status dot: green on the hourly cadence, amber/red (with a note) when
# it falls behind. Ridership gets no dot: the MBTA publishes it
# monthly, weeks after the month ends.
alerts_freshness = freshness(alerts_updated, now)
alerts_note = {'fresh': '', 'late': ' · running behind', 'stale': ' · may be out of date'}[alerts_freshness]
alerts_status = f'Alerts updated {alerts_updated.tz_convert(TIMEZONE).strftime("%b %-d, %-I:%M %p ET")}{alerts_note}'

st.markdown(f"""
<div class="hero">
  <div class="lines">{"".join(f'<span style="background:{c}"></span>' for c in LINE_COLORS.values())}</div>
  <h1>MBTA Reliability &amp; Ridership</h1>
  <p>Service incidents and weather on Boston's four subway lines, and riders on every MBTA mode.</p>
  <div class="status">
    <span class="dot {alerts_freshness}">{alerts_status}</span>
    <span>Ridership through {ridership_through.strftime("%b %-d, %Y")}</span>
    <span>Built by <a href="{GITHUB_URL}" target="_blank" rel="noopener">{AUTHOR}</a> ·
      <a href="{REPO_URL}" target="_blank" rel="noopener">Source on GitHub</a></span>
  </div>
</div>
""", unsafe_allow_html=True)

selected_lines = st.pills(
    'Lines', LINES, selection_mode='multi', default=LINES,
    key='line_filter', label_visibility='collapsed',
) or LINES  # Nothing selected → show everything rather than an empty page

incidents = incidents_all[incidents_all['line_name'].isin(selected_lines)]
incident_stations = incident_stations_all[incident_stations_all['line_name'].isin(selected_lines)]
incident_periods = incident_periods_all[incident_periods_all['line_name'].isin(selected_lines)]
stations =stations_all[stations_all['line_name'].isin(selected_lines)]
shapes = shapes_all[shapes_all['line_name'].isin(selected_lines)]
delay_estimates = delay_estimates_all[delay_estimates_all['line_name'].isin(selected_lines)]
ridership = ridership_all[ridership_all['line_name'].isin(selected_lines)]

# ══════════════════════════════════════════════════════════════════════════════
# 2. Service status
# ══════════════════════════════════════════════════════════════════════════════

section('Service status', 'Incidents on the selected lines right now, and planned work ahead.')

# Incidents in force now or still to come, dated by the period that matters
# now: planned work posted for several weekends shows the current or next one.
current = in_force(incidents, incident_periods, now)
active = one_row_per_incident(current[current['is_active']]).sort_values('incident_start_at', ascending=False)

upcoming = one_row_per_incident(current[~current['is_active']]).sort_values('incident_start_at')
upcoming_30d = upcoming[upcoming['incident_start_at'] <= now + pd.Timedelta(days=30)]

# Incidents that have started. `started` keeps gold's incident × route rows (for
# per-line counts); `started_events` has one row per incident, so an event on
# four Green Line branches counts once everywhere incidents are counted.
started = incidents[incidents['incident_start_at'] <= now]
started_events = one_row_per_incident(started)
last_30 = started_events[started_events['incident_start_at'] > now - pd.Timedelta(days=30)]
prior_30 = started_events[(started_events['incident_start_at'] <= now - pd.Timedelta(days=30))
                          & (started_events['incident_start_at'] > now - pd.Timedelta(days=60))]

# Change vs the previous 30 days; fewer incidents is good (green).
if len(prior_30):
    change = (len(last_30) / len(prior_30) - 1) * 100
    css = 'delta-up' if change <= 0 else 'delta-down'
    arrow = '▼' if change <= 0 else '▲'
    trend = f'<span class="{css}">{arrow} {abs(change):.1f}%</span> vs prior 30 days'
else:
    trend = 'first 30 days of tracking'

active_lines = active['line_name'].nunique()
kpi_tiles([
    dict(label='Active now', value=f'{len(active)}',
         sub=f"on {active_lines} line{'s' if active_lines != 1 else ''}" if len(active) else 'all clear'),
    dict(label='Planned work · next 30 days', value=f'{len(upcoming_30d)}',
         sub=(f"next starts {fmt_day(upcoming_30d['incident_start_at'].iloc[0])}"
              if len(upcoming_30d) else 'none scheduled')),
    dict(label='Incidents · last 30 days', value=f'{len(last_30)}', sub=trend),
    dict(label='Median duration · last 30 days', value=fmt_duration(last_30['incident_duration_minutes'].median()),
         sub='first alert to all-clear'),
])

now_col, next_col = st.columns(2, gap='medium')

with now_col:
    with st.container(key='card_active'):
        card_title('Happening now', f"{len(active)} active incident{'s' if len(active) != 1 else ''}")
        incident_list(
            active,
            lambda r: (f"Since {fmt_day(r['incident_start_at'])} · "
                       + (f"until {fmt_day(r['incident_end_at'])}" if pd.notna(r['incident_end_at'])
                          else 'no end time posted')
                       + f" · {fmt_duration(r['incident_duration_minutes'])}"
                       + (' so far' if pd.isna(r['incident_end_at']) else '')),
            'No active incidents on the selected lines.',
        )

with next_col:
    with st.container(key='card_upcoming'):
        card_title('Coming up', f'{len(upcoming)} planned by the MBTA')
        incident_list(
            upcoming,
            lambda r: (f"Starts {fmt_day(r['incident_start_at'])} · "
                       + (f"until {fmt_day(r['incident_end_at'])} · {fmt_duration(r['incident_duration_minutes'])}"
                          if pd.notna(r['incident_end_at']) else 'no end time posted')),
            'No planned work announced.',
        )

# ══════════════════════════════════════════════════════════════════════════════
# 3. Stations affected
# ══════════════════════════════════════════════════════════════════════════════

# Trailing 12 months — or since continuous alert tracking began, while that's
# more recent. Every incident's stations are known (its
# JSON, or LAMP's entities).
stations_window_start = max(coverage_start, now - pd.DateOffset(months=12))
stations_window_label = (
    'Trailing 12 months' if stations_window_start > coverage_start
    else f'Since continuous alert tracking began on {fmt_day(coverage_start)}, {coverage_start.year}'
)

section(
    'Stations affected',
    "Stations named in the selected lines' incident alerts. Most delays are line-wide and name no station.",
)


def station_markers(hits, planned=False):
    """
    One marker per station × line, listing every incident in `hits` affecting
    it (with its start date when `planned`).
    """
    detail = [
        f'{route}: {effect}' + ('' if both else f' (toward {dest})')
        + (f' · starts {fmt_day(start)}' if planned else '')
        for route, effect, both, dest, start in zip(
            hits['route_name'], hits['incident_effect'], hits['is_both_directions'],
            hits['direction_destination'], hits['incident_start_at'], strict=True)
    ]
    return (hits.assign(detail=detail).groupby(['station_id', 'line_name'], as_index=False)
            .agg(station_name=('station_name', 'first'), lat=('station_latitude', 'first'),
                 lon=('station_longitude', 'first'), detail=('detail', lambda x: '<br>'.join(sorted(set(x))))))


# Stations hit by incidents in force right now, and by planned ones starting
# within 30 days, on the same dates as the status cards above.
hits = (incident_stations.drop(columns=['incident_start_at', 'incident_end_at'])
        .merge(current[['incident_id', 'route_name', 'incident_start_at', 'incident_end_at', 'is_active']],
               on=['incident_id', 'route_name']))
active_hits = hits[hits['is_active']]
planned_hits = hits[~hits['is_active'] & (hits['incident_start_at'] <= now + pd.Timedelta(days=30))]


def station_map(backdrop, shapes, markers, height=560):
    """
    The network as a transit map: every station a dot in its line's color, the
    line itself a faint path behind them, and the base map dimmed with no place
    names. The map names the system instead (MAP_LABELS). Affected stations are
    larger and outlined in white, each run of them named at its ends
    (run_end_labels), and every one shows its details on hover. Map labels use
    Open Sans: they're drawn from the map's font server, which doesn't have the
    page's font.
    """
    # Where each affected station's name goes: '' for none, mid-run.
    named_at = {}
    for line, hit in markers.groupby('line_name'):
        ends = run_end_labels(shapes.loc[shapes['line_name'] == line, 'points'],
                              backdrop[backdrop['line_name'] == line], set(hit['station_id']))
        named_at.update({(line, station_id): position for station_id, position in ends.items()})
    markers = markers.assign(position=[named_at.get(key, '') for key in
                                       zip(markers['line_name'], markers['station_id'], strict=True)])

    fig = go.Figure()
    for line in LINES:
        paths = shapes[shapes['line_name'] == line]['points']
        if paths.empty:
            continue
        # One trace per line: a None between paths lifts the pen.
        lats = [lat for path in paths for lat in [point[0] for point in path] + [None]]
        lons = [lon for path in paths for lon in [point[1] for point in path] + [None]]
        # Faint, so the stations stay the subject.
        fig.add_trace(go.Scattermap(lat=lats, lon=lons, mode='lines', opacity=0.3,
                                    line=dict(color=LINE_COLORS[line], width=2), hoverinfo='skip'))

    for line in LINES:
        bg = backdrop[backdrop['line_name'] == line]
        if len(bg):
            # A soft light halo, so official Blue stays visible on the dark map.
            fig.add_trace(go.Scattermap(
                lat=bg['station_latitude'], lon=bg['station_longitude'], mode='markers',
                marker=dict(size=8, color=INK, opacity=0.25), hoverinfo='skip',
            ))
            fig.add_trace(go.Scattermap(
                lat=bg['station_latitude'], lon=bg['station_longitude'], mode='markers',
                marker=dict(size=6, color=LINE_COLORS[line], opacity=1),
                hovertext=bg['station_name'] + ' · ' + line, hoverinfo='text',
            ))

    # Orienting names, grouped by position (a trace takes only one), except
    # where an affected station's name replaces one. Drawn before the affected
    # stations: where labels overlap, the map keeps the last drawn, and an
    # affected station's name must always win. An invisible marker, because a
    # text-only trace doesn't draw on this map type.
    named = backdrop[backdrop['station_name'].isin(
        set(MAP_LABELS) - set(markers.loc[markers['position'] != '', 'station_name']))]
    named = named.drop_duplicates('station_name')
    named = named.assign(position=named['station_name'].map(MAP_LABELS))
    for position, group in named.groupby('position'):
        fig.add_trace(go.Scattermap(
            lat=group['station_latitude'], lon=group['station_longitude'], mode='markers+text',
            marker=dict(size=1, opacity=0),
            text=group['station_name'], textposition=position,
            textfont=dict(color=INK_2, size=11, family='Open Sans Regular'), hoverinfo='skip',
        ))

    for line in LINES:
        hit = markers[markers['line_name'] == line]
        if len(hit):
            # A white outline under each affected station, then the
            # station itself: its neighbors share its color, so color
            # can't mark it. One trace per name position (a trace takes
            # only one), and none for mid-run stations.
            fig.add_trace(go.Scattermap(
                lat=hit['lat'], lon=hit['lon'], mode='markers',
                marker=dict(size=12, color=INK, opacity=1), hoverinfo='skip',
            ))
            for position, group in hit.groupby('position'):
                fig.add_trace(go.Scattermap(
                    lat=group['lat'], lon=group['lon'], mode='markers+text' if position else 'markers',
                    marker=dict(size=9, color=LINE_COLORS[line], opacity=1),
                    text=group['station_name'], textposition=position or None,
                    textfont=dict(color=INK, size=11, family='Open Sans Bold'),
                    hovertext='<b>' + group['station_name'] + '</b><br>' + group['detail'], hoverinfo='text',
                ))
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        hoverlabel=dict(bgcolor='#1c2027', bordercolor=BORDER, font=dict(family=FONT, color=INK, size=12)),
        # Zoom buttons stacked in the corner, in the page's muted ink.
        modebar=dict(orientation='v', bgcolor='rgba(19,22,27,0.85)', color=INK_2, activecolor=INK),
        # Keep the reader's zoom when the line filter or
        # view toggle reruns the page.
        uirevision='station_map',
        # The middle of the system, zoomed so the whole network fits the map's
        # height: Braintree (42.21°N) to Oak Grove (42.44°N), Riverside to
        # Wonderland. Map zoom levels use 512px tiles. On a phone the east and
        # west ends sit just off screen; drag or zoom out to see them. No town
        # names on the base map, so nothing outshines the stations.
        map=dict(
            style='carto-darkmatter-nolabels', center=dict(lat=42.322, lon=-71.12), zoom=10.2,
            # A veil over the base map, under the data, so
            # roads recede behind the stations.
            layers=[dict(sourcetype='geojson', type='fill', below='traces', color=PAGE, opacity=0.55, source=dict(
                type='Feature', properties={}, geometry=dict(
                    type='Polygon', coordinates=[[[-180, -85], [180, -85], [180, 85], [-180, 85], [-180, -85]]])))],
        ),
    )
    return fig


# The map gets two thirds of the width; the ranking is a short list.
map_col, rank_col = st.columns([2, 1], gap='medium')

with map_col:
    with st.container(key='card_station_map'):
        view = st.segmented_control(
            'Map view', ['Right now', 'Planned · next 30 days'], default='Right now',
            key='station_view', label_visibility='collapsed',
        ) or 'Right now'  # Clicking the selected option clears it; fall back to the default
        # The view picks which incidents' stations to outline: active now, or
        # planned to start within 30 days.
        planned = view != 'Right now'
        hits = planned_hits if planned else active_hits
        markers = station_markers(hits, planned=planned)
        n_stations = markers['station_id'].nunique()
        n_incidents = hits['incident_id'].nunique()
        card_title(
            'Planned work, next 30 days' if planned else 'Affected right now',
            (f"{n_stations} station{'s' if n_stations != 1 else ''} · "
             f"{n_incidents} incident{'s' if n_incidents != 1 else ''} · hover or tap a station for details")
            if n_stations else ('No planned work naming stations' if planned else 'No stations affected right now'),
        )
        show(station_map(stations, shapes, markers), config=MAP_CONFIG)
        st.markdown(
            '<div class="map-credit">Map data © <a href="https://www.openstreetmap.org/copyright">'
            'OpenStreetMap</a> contributors · © <a href="https://carto.com/attributions">CARTO</a></div>',
            unsafe_allow_html=True,
        )

with rank_col:
    with st.container(key='card_station_rank'):
        # Incidents active at any point in the window that have started; an
        # incident counts once per station however many branches it covered.
        window_hits = incident_stations[
            (incident_stations['incident_start_at'] <= now)
            & (incident_stations['incident_end_at'].isna()
               | (incident_stations['incident_end_at'] >= stations_window_start))
        ]
        ranked = (window_hits.groupby('station_name')['incident_id'].nunique()
                  .sort_values(ascending=False).head(15))
        card_title('Most affected stations', f'{stations_window_label} · incidents naming each station')
        if ranked.empty:
            st.markdown('<div class="empty">No station-level incidents yet on the selected lines.</div>',
                        unsafe_allow_html=True)
        else:
            show(ranked_bars(
                ranked.index.tolist(), ranked.tolist(),
                [f'{n}' for n in ranked],
                [f"{station}<br>{n} incident{'s' if n != 1 else ''}" for station, n in ranked.items()],
            ))

# ══════════════════════════════════════════════════════════════════════════════
# 4. Incident patterns
# ══════════════════════════════════════════════════════════════════════════════

# Trailing 12 months — or since alert tracking began, while that's more recent.
year_ago = now - pd.DateOffset(months=12)
window_start = max(coverage_start, year_ago)
history = started[started['incident_start_at'] >= window_start]                     # incident × route
history_events = started_events[started_events['incident_start_at'] >= window_start]  # one per incident
window_label = ('Trailing 12 months' if window_start == year_ago
                else f'Since continuous alert tracking began on {fmt_day(coverage_start)}, {coverage_start.year}'
                     ' (less than 12 months ago)')

section(
    'Incident patterns',
    f'{window_label}. Re-posted alerts for the same event count once.',
)

if history.empty:
    st.markdown('<div class="empty">No incidents recorded yet.</div>', unsafe_allow_html=True)
else:
    # ── When: incidents per week ──────────────────────────────────────────────
    week_col, line_col = st.columns([3, 2], gap='medium')
    with week_col:
        with st.container(key='card_weekly'):
            card_title('Incidents per week', 'By the week the incident started · partial weeks dimmed')
            weeks = (history_events['incident_start_at'].dt.tz_convert(TIMEZONE).dt.tz_localize(None)
                     .dt.to_period('W-SUN').dt.start_time)
            weekly = weeks.value_counts().sort_index()
            weekly = weekly.reindex(pd.date_range(weekly.index.min(), weekly.index.max(), freq='7D'), fill_value=0)
            # Partial weeks — the one coverage starts in (unless it starts on a
            # Monday) and the current one — are drawn lighter.
            this_week = now.tz_convert(TIMEZONE).tz_localize(None).to_period('W-SUN').start_time
            first_day = window_start.tz_convert(TIMEZONE).tz_localize(None).normalize()
            first_week = first_day.to_period('W-SUN').start_time if first_day.day_of_week else None
            partial = {this_week, first_week}
            opacity = [0.45 if w in partial else 1.0 for w in weekly.index]
            week_note = {this_week: ' (so far)', first_week: ' (partial)'}
            fig = go.Figure(go.Bar(
                x=weekly.index, y=weekly.values,
                marker=dict(color=ACCENT, cornerradius=4, opacity=opacity),
                hovertext=[f"Week of {w:%b %-d}{week_note.get(w, '')}<br>{n} incidents"
                           for w, n in weekly.items()],
                hoverinfo='text',
            ))
            style(fig, height=260)
            fig.update_xaxes(tickformat='%b %-d', gridcolor='rgba(0,0,0,0)')
            show(fig)

    # ── Where: incidents by line ──────────────────────────────────────────────
    with line_col:
        with st.container(key='card_by_line'):
            card_title('Incidents by line', "On any of the line's routes")
            by_line = history.groupby('line_name')['incident_id'].nunique().reindex(selected_lines).fillna(0)
            show(share_bars(by_line, colors=[LINE_COLORS[line] for line in by_line.index], height=260))

    # ── Why: causes and effects ───────────────────────────────────────────────
    cause_col, effect_col = st.columns(2, gap='medium')
    cause_counts = history_events['incident_cause'].value_counts()
    top_causes = cause_counts.head(7)
    if len(cause_counts) > 7:
        top_causes['Other'] = cause_counts.iloc[7:].sum()

    with cause_col:
        with st.container(key='card_causes'):
            card_title('Incidents by cause', 'Top causes · the rest grouped as Other')
            show(share_bars(top_causes))

    with effect_col:
        with st.container(key='card_effects'):
            card_title('Incidents by effect', 'How service was affected')
            effects = history_events['incident_effect'].value_counts()
            show(share_bars(effects, height=max(180, 34 * len(top_causes) + 30)))  # match the causes card

    # ── How long, and where each cause hits ───────────────────────────────────
    dur_col, mix_col = st.columns(2, gap='medium')
    named_causes = [c for c in top_causes.index if c != 'Other']

    with dur_col:
        with st.container(key='card_duration'):
            card_title('Duration by cause', 'Median · first alert to all-clear')
            # One labeled dot per named cause, in the
            # same order as the cause chart.
            dur = (history_events[history_events['incident_cause'].isin(named_causes)]
                   .groupby('incident_cause')['incident_duration_minutes'].median()
                   .reindex(named_causes))
            fig = go.Figure(go.Scatter(
                x=dur.values, y=dur.index, mode='markers+text',
                marker=dict(color=ACCENT, size=11, line=dict(color=CARD, width=2)),
                text=[LABEL_GAP + fmt_duration(v) for v in dur.values], textposition='middle right',
                textfont=dict(color=INK_2, size=11), cliponaxis=False,
                hovertext=[f'{c}: median {fmt_duration(v)}' for c, v in dur.items()], hoverinfo='text',
            ))
            style(fig, height=max(180, 34 * len(named_causes) + 40))
            if dur.max() < 1440:
                # Everything under a day: linear hours read more naturally.
                hours = int(np.ceil(dur.max() / 60)) + 1
                fig.update_xaxes(range=[0, hours * 60 * 1.15], tickvals=[h * 60 for h in range(0, hours + 1)],
                                 ticktext=[f'{h} hr' for h in range(0, hours + 1)])
            else:
                # Mixed hours and days: log scale keeps short causes readable.
                fig.update_xaxes(type='log', tickvals=[60, 360, 1440, 10080, 43200],
                                 ticktext=['1 hr', '6 hr', '1 day', '1 wk', '1 mo'],
                                 range=[np.log10(20), np.log10(200000)])
            fig.update_yaxes(autorange='reversed', gridcolor='rgba(0,0,0,0)', tickfont=dict(color=INK_2, size=12))
            show(fig)

    with mix_col:
        with st.container(key='card_mix'):
            card_title('Cause mix by line', "Share of each line's incidents · top causes")
            # Heatmap of cause × line: each cell is that cause's share of the
            # line's incidents, so lines of different sizes compare fairly.
            mix = (history[history['incident_cause'].isin(named_causes)]
                   .groupby(['incident_cause', 'line_name'])['incident_id'].nunique().unstack(fill_value=0)
                   .reindex(index=named_causes, columns=selected_lines, fill_value=0))
            mix_pct = mix / history.groupby('line_name')['incident_id'].nunique().reindex(selected_lines) * 100
            fig = go.Figure(go.Heatmap(
                z=mix_pct.values, x=list(mix_pct.columns), y=mix_pct.index,
                colorscale=SEQUENTIAL, showscale=False, xgap=3, ygap=3,
                text=[[f'{v:.0f}%' for v in row] for row in mix_pct.values], texttemplate='%{text}',
                textfont=dict(size=11, color=INK),
                hovertemplate='%{y} · %{x}<br>%{text} of incidents<extra></extra>',
            ))
            style(fig, height=max(180, 34 * len(named_causes) + 40))
            fig.update_yaxes(autorange='reversed', gridcolor='rgba(0,0,0,0)', tickfont=dict(color=INK_2, size=12))
            fig.update_xaxes(side='top', gridcolor='rgba(0,0,0,0)', tickfont=dict(color=INK_2, size=12),
                             tickvals=list(mix_pct.columns),
                             ticktext=[line.replace(' ', '<br>') for line in mix_pct.columns])
            show(fig)

    # ── Posted end times against the all-clear ────────────────────────────────
    with st.container(key='card_estimates'):
        card_title('Posted end times vs the all-clear',
                   'Subway delays · the end the MBTA first posted · LAMP archive, up to a week behind')
        # An alert naming two lines counts once.
        est = delay_estimates[delay_estimates['alert_created_at'] >= window_start].drop_duplicates('alert_id')
        if est.empty:
            st.markdown('<div class="empty">No delays with a posted end yet.</div>', unsafe_allow_html=True)
        else:
            miss = (est['estimated_minutes'] - est['actual_minutes']).abs()
            kpi_tiles([
                dict(label='First posted end', value=fmt_duration(est['estimated_minutes'].median()),
                     sub='Median, from posting'),
                dict(label='Actual all-clear', value=fmt_duration(est['actual_minutes'].median()),
                     sub='Median, from posting'),
                dict(label='Typical miss', value=fmt_duration(miss.median()), sub='Median per delay, early or late'),
                dict(label='Within 15 minutes', value=f'{(miss <= 15).mean() * 100:.0f}%',
                     sub=f'Of {fmt_count(len(est))} delays'),
            ])

# ══════════════════════════════════════════════════════════════════════════════
# 5. Disruption by year
# ══════════════════════════════════════════════════════════════════════════════

# Yearly charts start with the first whole calendar year of continuous alert
# history and end with the year in progress, dimmed and labeled "so far".
coverage_day = coverage_start.tz_convert(TIMEZONE)
first_full_year = coverage_day.year + (0 if (coverage_day.month, coverage_day.day) == (1, 1) else 1)
this_year = now.tz_convert(TIMEZONE).year
years = list(range(first_full_year, this_year + 1))
year_labels = [f'{y} so far' if y == this_year else str(y) for y in years]
year_opacity = [0.45 if y == this_year else 1.0 for y in years]


def year_axis(fig):
    """
    The yearly charts' x-axis. Categories, because left to guess, Plotly reads
    years as dates and drops "2026 so far"; "so far" on its own line, so labels
    stay level at phone width.
    """
    fig.update_xaxes(type='category', tickmode='array', tickvals=year_labels, tickangle=0,
                     ticktext=[label.replace(' so far', '<br>so far') for label in year_labels],
                     gridcolor='rgba(0,0,0,0)', tickfont=dict(color=INK_2, size=11))


# Delay lengths, an ordered scale: one violet hue, brighter = longer.
DELAY_BANDS = ['Under 30 min', '30 min – 1 hr', '1 hr or more']
DELAY_COLORS = ['#5348a8', '#7f74e0', '#b8b0f5']

section(
    'Disruption by year',
    f'Every full year since {first_full_year}, the first full year of alert history, and {this_year} so far '
    '(dimmed).',
)

delay_col, outage_col = st.columns(2, gap='medium')

# ── Delays per year, by how long they lasted ──────────────────────────────────
with delay_col:
    with st.container(key='card_delay_lengths'):
        card_title('Delays per year, by length', 'First alert to all-clear')
        delays = started_events[started_events['incident_effect'] == 'Delay'].assign(
            year=lambda d: d['incident_start_at'].dt.tz_convert(TIMEZONE).dt.year,
            band=lambda d: pd.cut(d['incident_duration_minutes'], [-np.inf, 30, 60, np.inf], right=False,
                                  labels=DELAY_BANDS))
        counts = (delays[delays['year'].isin(years)].groupby(['year', 'band'], observed=False).size()
                  .unstack(fill_value=0).reindex(index=years, columns=DELAY_BANDS, fill_value=0))
        fig = go.Figure()
        # Longest delays at the bottom, against the baseline,
        # so their growth reads directly.
        for band, color in reversed(list(zip(DELAY_BANDS, DELAY_COLORS, strict=True))):
            fig.add_trace(go.Bar(
                x=year_labels, y=counts[band], name=band,
                marker=dict(color=color, opacity=year_opacity, line=dict(color=CARD, width=2)),
                hovertemplate=f'%{{x}} · {band}: %{{y:,}} delays<extra></extra>',
            ))
        totals = counts.sum(axis=1)
        fig.add_trace(go.Scatter(
            x=year_labels, y=totals, mode='text', text=[f'{n:,}' for n in totals], textposition='top center',
            textfont=dict(color=INK_2, size=11), showlegend=False, hoverinfo='skip', cliponaxis=False,
        ))
        style(fig, height=300, legend=True)
        fig.update_layout(barmode='stack', barcornerradius=4, legend_traceorder='reversed')
        year_axis(fig)
        count_axis(fig, totals.max() * 1.12)
        show(fig)
        long_ones = counts['1 hr or more']
        if len(years) > 2:
            last_full = years[-2]
            st.caption(f'Delays of an hour or more: {long_ones[first_full_year]:,} in {first_full_year}, '
                       f"{long_ones[last_full]:,} in {last_full}. Short ones held steadier, so the rise isn't "
                       'just more alerts being posted.')

# ── Out-of-service hours per year, by line ────────────────────────────────────
# Shuttles and suspensions together: the MBTA's labels for the two overlap (the
# 2022 Orange Line shutdown, run with shuttle buses, was posted as a
# suspension), and either way trains weren't running on part of the line.
OUT_OF_SERVICE_EFFECTS = ['Shuttle', 'Suspension']

with outage_col:
    with st.container(key='card_out_of_service'):
        card_title('Out-of-service hours per year',
                   'Hours with part of the line suspended or on shuttle buses · overlaps count once')
        # By period, so planned work posted for several weekends counts only
        # those weekends.
        outages = incident_periods[incident_periods['incident_effect'].isin(OUT_OF_SERVICE_EFFECTS)].rename(
            columns={'period_start_at': 'start_at', 'period_end_at': 'end_at'})
        hours = (hours_by_year(outages[['line_name', 'start_at', 'end_at']], now)
                 .pivot(index='year', columns='line_name', values='hours')
                 .reindex(index=years, columns=selected_lines).fillna(0))
        fig = go.Figure()
        for line in selected_lines:
            fig.add_trace(go.Bar(
                x=year_labels, y=hours[line], name=line,
                marker=dict(color=LINE_COLORS[line], opacity=year_opacity, line=dict(color=CARD, width=2)),
                hovertemplate=f'%{{x}} · {line}: %{{y:,.0f}} hours<extra></extra>',
            ))
        totals = hours.sum(axis=1)
        style(fig, height=300, legend=True)
        # Legend in line order, as everywhere else
        # (Plotly reverses it for stacks).
        fig.update_layout(barmode='stack', barcornerradius=4, legend_traceorder='normal')
        year_axis(fig)
        in_thousands = count_axis(fig, max(totals.max(), 1) * 1.12)
        # Each year's total, in the axis's own units: 8.3K beside a K axis,
        # 1,926 beside one in hundreds (a single line's hours).
        fig.add_trace(go.Scatter(
            x=year_labels, y=totals, mode='text', text=[fmt_count(h, thousands=in_thousands) for h in totals],
            textposition='top center', textfont=dict(color=INK_2, size=11), showlegend=False, hoverinfo='skip',
            cliponaxis=False,
        ))
        show(fig)

# ══════════════════════════════════════════════════════════════════════════════
# 6. Delays riders feel
# ══════════════════════════════════════════════════════════════════════════════

# Alerts count what the MBTA posts. Two of its own measures reach what riders
# felt (decision 0019): how much longer each trip took than normal on the Red,
# Orange, and Blue Lines, which counts slow zones it rarely posted, and its
# monthly rider survey. Both cards start when the trip times do, so their
# months line up; each takes one source.
feel_start = trip_times_all['month_start'].min()
feel_end = max(trip_times_all['month_start'].max(), satisfaction_all['survey_month'].max())
trip_time_lines = [line for line in selected_lines if line in set(trip_times_all['line_name'])]


def feel_axis(fig):
    """The two cards' shared x-axis: the same months, a tick each January."""
    pad = (feel_end - feel_start) * 0.01
    fig.update_xaxes(range=[feel_start - pad, feel_end + pad], tickformat='%Y', dtick='M12', tickangle=0,
                     gridcolor='rgba(0,0,0,0)', showspikes=True, spikemode='across', spikethickness=1,
                     spikecolor=AXIS, spikedash='solid')


section(
    'Delays riders feel',
    "How much longer trips took than normal on the Red, Orange, and Blue Lines, from the MBTA's estimates, and "
    'what riders tell its monthly survey.',
)

trip_col, survey_col = st.columns(2, gap='medium')

# ── Extra minutes per trip ────────────────────────────────────────────────────
# Trip time is wait plus ride; normal is the MBTA's baseline for the line,
# half hour, and direction. Months are rider-weighted: total extra minutes
# over total riders.
with trip_col:
    with st.container(key='card_trip_times'):
        card_title('Extra minutes per trip', 'Trip time over normal, per rider, each month · waiting and riding')
        if not trip_time_lines:
            st.caption("The MBTA doesn't estimate trip times for the Green Line.")
        else:
            trips = trip_times_all[trip_times_all['line_name'].isin(trip_time_lines)].sort_values('month_start')
            trips = trips.assign(extra=trips['extra_minutes'] / trips['riders'],
                                 within_5=trips['riders_within_5'] / trips['riders'] * 100)
            fig = go.Figure()
            ends = []
            for line in trip_time_lines:
                t = trips[trips['line_name'] == line]
                fig.add_trace(go.Scatter(
                    x=t['month_start'], y=t['extra'], name=line, mode='lines',
                    line=dict(color=LINE_COLORS[line], width=2), customdata=t['within_5'],
                    hovertemplate=f'{line}: %{{y:.1f}} min · %{{customdata:.0f}}% within 5 of normal<extra></extra>',
                ))
                ends.append((line, t['month_start'].iloc[-1], t['extra'].iloc[-1], line))
            top = trips['extra'].max() * 1.08
            label_line_ends(fig, ends, top)
            style(fig, height=300)
            fig.update_layout(margin=dict(l=4, r=96, t=8, b=4), hovermode='x unified')
            feel_axis(fig)
            # A month can run under normal (a little below zero); the axis
            # shows it rather than clip it.
            fig.update_yaxes(range=[min(trips['extra'].min() * 1.2, 0), top], ticksuffix=' min')
            fig.add_hline(y=0, line=dict(color=AXIS, width=1))
            show(fig)
            # Each line's worst full year against its last 12 months.
            through = trips['through_date'].max()
            full_years = trips[trips['month_start'].dt.year < through.year]
            recent = trips[trips['month_start'] > through - pd.DateOffset(months=12)]
            by_year = full_years.groupby(['line_name', full_years['month_start'].dt.year])[
                ['extra_minutes', 'riders']].sum()
            by_year = (by_year['extra_minutes'] / by_year['riders']).rename('extra').reset_index()
            now_extra = recent.groupby('line_name')[['extra_minutes', 'riders']].sum()
            now_extra = now_extra['extra_minutes'] / now_extra['riders']
            worst = by_year.loc[by_year.groupby('line_name')['extra'].idxmax()].set_index('line_name')
            st.caption(f'Worst full year, then the 12 months to {through:%b %Y}: '
                       + '; '.join(f"{line} {fmt_minutes(worst.loc[line, 'extra'])} min "
                                   f"({worst.loc[line, 'month_start']}) → {fmt_minutes(now_extra[line])}"
                                   for line in trip_time_lines)
                       + '. Slow zones count here, though they rarely appeared in alerts.')

# ── What riders say ───────────────────────────────────────────────────────────
# The share answering positively (the top three of seven answers). Two of the
# survey's four questions: the one on reliability, and the overall rating.
SURVEY_SERIES = {'Agree the MBTA is reliable': ACCENT, 'Satisfied with the MBTA overall': '#c4bdf5'}
RELIABLE = 'Agree the MBTA is reliable'

with survey_col:
    with st.container(key='card_survey'):
        card_title('What riders say', "Share answering positively, each month · the MBTA's survey, every mode")
        fig = go.Figure()
        for label, color in SURVEY_SERIES.items():
            s = (satisfaction_all[(satisfaction_all['question_label'] == label)
                                  & (satisfaction_all['survey_month'] >= feel_start)].sort_values('survey_month'))
            fig.add_trace(go.Scatter(
                x=s['survey_month'], y=s['positive_share'] * 100, name=label, mode='lines',
                line=dict(color=color, width=2), customdata=s['respondents'],
                hovertemplate=f'{label}: %{{y:.0f}}% of %{{customdata:,}}<extra></extra>',
            ))
        style(fig, height=300, legend=True)
        fig.update_layout(hovermode='x unified')
        feel_axis(fig)
        fig.update_yaxes(range=[0, 100], ticksuffix='%', dtick=25)
        show(fig)
        # The reliability question by year: before the pandemic, its low, and
        # the last 12 months.
        reliable = satisfaction_all[satisfaction_all['question_label'] == RELIABLE]
        by_year = reliable.groupby(reliable['survey_month'].dt.year)['positive_share'].mean() * 100
        survey_through = reliable['survey_month'].max()
        before = by_year[by_year.index < 2020]
        since = by_year[(by_year.index >= feel_start.year) & (by_year.index < survey_through.year)]
        latest = reliable[reliable['survey_month'] > survey_through - pd.DateOffset(months=12)]['positive_share']
        st.caption(f'Agreeing the MBTA is reliable: {before.min():.0f}–{before.max():.0f}% a year before the '
                   f'pandemic, {since.min():.0f}% in {since.idxmin()}, {latest.mean() * 100:.0f}% in the 12 months '
                   f'to {survey_through:%b %Y}. About {round(reliable["respondents"].median(), -2):,.0f} riders answer '
                   'each month.')

# ══════════════════════════════════════════════════════════════════════════════
# 7. Subway ridership
# ══════════════════════════════════════════════════════════════════════════════

# Non-breaking spaces keep "Sep 2026" and "▲ 12.6%" whole when tiles wrap.
NBSP = '\u00a0'

# The last full year before the pandemic: what ridership is measured
# against, "how far back is it?"
BASELINE_YEAR = 2019

# One-day events: (date, what happened, kind, short label for the daily view).
# Add a day as a line here. Kinds:
#   crowd    a crowd riding in, measured in "Days that moved ridership"
#   snow     a storm keeping riders home, measured there too, with its snowfall
#            from the weather data
#   context  marked in the daily view only: its day can't be measured fairly
#            (the BLM march came as reopening lifted every day that week)
RIDERSHIP_DAYS = [
    ('2015-02-04', 'Patriots parade', 'crowd', 'Patriots parade'),
    ('2017-02-07', 'Patriots parade', 'crowd', 'Patriots parade'),
    ('2019-02-05', 'Patriots parade', 'crowd', 'Patriots parade'),
    ('2018-10-31', 'Red Sox parade', 'crowd', 'Red Sox parade'),
    ('2024-06-21', 'Celtics parade', 'crowd', 'Celtics parade'),
    ('2017-01-21', "Women's March", 'crowd', "Women's March"),
    ('2025-04-05', 'Hands Off rally', 'crowd', 'Hands Off'),
    ('2025-06-14', 'No Kings and Pride parade', 'crowd', 'No Kings, Pride'),
    ('2025-10-18', 'No Kings protest', 'crowd', 'No Kings'),
    ('2026-03-28', 'No Kings protest', 'crowd', 'No Kings'),
    ('2026-07-11', 'Tall ships, Sail Boston', 'crowd', 'Tall ships'),
    ('2015-01-27', 'Blizzard, MBTA closed', 'snow', 'Blizzard'),
    ('2018-03-13', "Nor'easter", 'snow', "Nor'easter"),
    ('2026-02-23', 'Snowstorm', 'snow', 'Snowstorm'),
    ('2020-05-31', 'BLM march', 'context', 'BLM march'),
]
EVENT_DAYS = (pd.DataFrame(RIDERSHIP_DAYS, columns=['date', 'label', 'kind', 'short'])
              .assign(date=lambda d: pd.to_datetime(d['date'])))

if ridership.empty:
    section('Subway ridership')
    st.markdown('<div class="empty">No ridership data available yet.</div>', unsafe_allow_html=True)
    st.stop()

# Complete months only (the MBTA publishes whole months, but guard the edges).
month_days = ridership.groupby(['line_name', 'month'])['service_date'].nunique().rename('days').reset_index()
month_days = month_days[month_days['days'] == month_days['month'].dt.days_in_month]
full_months = ridership.merge(month_days[['line_name', 'month']], on=['line_name', 'month'])
latest_month = full_months['month'].max()
latest_month_label = latest_month.strftime(f'%b{NBSP}%Y')
year_ago_label = (latest_month - 12).strftime(f'%b{NBSP}%Y')

baseline_month = pd.Period(year=BASELINE_YEAR, month=latest_month.month, freq='M')
baseline_month_label = baseline_month.strftime(f'%b{NBSP}%Y')
archive_year = ridership_all['service_date'].min().year

# Ridership's window ends at the latest published day, not today (the MBTA
# publishes in irregular batches, weeks to months behind).
ridership_year_start = ridership_through - pd.DateOffset(months=12) + pd.Timedelta(days=1)

section(
    'Subway ridership',
    f'Fare-gate entries at subway stations, as averages per day with weekends included, through '
    f'{ridership_through:%b %Y}, the latest the MBTA has published. Buses, commuter rail, ferries, and the Green '
    "Line's street-level stops have no gates; every mode is in the last section.",
)

# Every day except federal holidays — for the comparisons (day of week, "% vs
# typical", "% vs calm days"), where a holiday isn't a typical day for its
# weekday. Volumes (the tiles, the monthly chart) count every day.
ordinary_days = ridership[~ridership['is_holiday']]

# ── Per-line tiles: the latest month vs a year earlier and the baseline year ──
def change_vs(current, earlier, label):
    """
    ▲ 12.6% vs Sep 2025, colored by direction; None if
    there's nothing to compare with.
    """
    if pd.isna(earlier) or not earlier:
        return None
    change = (current / earlier - 1) * 100
    return (f'<span class="{"delta-up" if change >= 0 else "delta-down"}">'
            f'{"▲" if change >= 0 else "▼"}{NBSP}{abs(change):.1f}%</span> vs{NBSP}{label}')


tiles = []
for line in selected_lines:
    days = ridership[ridership['line_name'] == line]
    current = days[days['month'] == latest_month]['gated_entries'].mean()
    prior_year = days[days['month'] == latest_month - 12]['gated_entries'].mean()
    baseline = days[days['month'] == baseline_month]['gated_entries'].mean()
    # The month is on the tile itself, so the number
    # never reads as a 12-month figure.
    tiles.append(dict(label=f'{line} · {latest_month_label}',
                      value=fmt_count(current) if pd.notna(current) else '—',
                      # One comparison per line, so neither wraps mid-way.
                      sub='<br>'.join(part for part in [
                          f'avg{NBSP}per{NBSP}day', change_vs(current, prior_year, year_ago_label),
                          change_vs(current, baseline, baseline_month_label)] if part),
                      color=LINE_COLORS[line]))
kpi_tiles(tiles)

# ── Monthly ridership: the last 2 years, or everything ────────────────────────
# Average per day, not monthly totals: months run 28–31 days, which would move
# totals with no change in ridership. The month's total is in the hover.
monthly = (full_months.groupby(['line_name', 'month'])['gated_entries']
           .agg(daily_avg='mean', total='sum').reset_index().sort_values(['line_name', 'month']))
# All history adds a trailing 12-month average: twelve consecutive whole
# months, so every point averages a full year of seasons
# and the long trend shows.
monthly['trend'] = monthly.groupby('line_name')['daily_avg'].transform(lambda s: s.rolling(12, min_periods=12).mean())
monthly['month_start'] = monthly['month'].dt.start_time

RECENT_RANGE, ALL_RANGE, DAILY_RANGE = '2 years', f'Since {archive_year}', 'Daily'
# Events that moved ridership month after month, each a hairline with a label
# above the plot: (date, label, anchor, shift in pixels, row). Only COVID: a
# storm or a shutdown moves a month or two, which reads as noise across all
# history. One-day events are in the daily view and in "Days that moved
# ridership" below.
RIDERSHIP_EVENTS = [('2020-03-01', 'COVID', 'right', 0, 0)]
# Height of a row of event labels, in pixels.
EVENT_ROW_PX = 15

# How far apart two daily-view labels can sit on one row, as a share of the
# span shown: about a label's width at phone width (150 days of a year
# shown). Past 2 years, days are too close to label; their dots keep hovers.
EVENT_GAP_SHARE = 0.41
EVENT_LABEL_MAX_DAYS = 2 * 366


def add_event_lines(fig, events, first, last):
    """
    Mark `events` (date, label, and anchor/shift/row as RIDERSHIP_EVENTS has
    them) between `first` and `last` with a hairline and a muted label above
    the plot. Returns how many rows of labels it used.
    """
    rows = 0
    for when, label, anchor, shift, row in events:
        if first <= when <= last:
            fig.add_vline(x=when, line=dict(color=GRID, width=1))
            fig.add_annotation(text=label, x=when, xref='x', y=1, yref='paper', yanchor='bottom',
                               xanchor=anchor, xshift=shift, yshift=row * EVENT_ROW_PX, showarrow=False,
                               font=dict(color=MUTED, size=11))
            rows = max(rows, row + 1)
    return rows


def monthly_figure(show_all):
    """
    Average entries per day, by month: the last 2 years, or (`show_all`)
    every month, faint, under its trailing 12-month average, with the events
    that moved whole months marked.
    """
    shown = monthly if show_all else monthly[monthly['month'] > latest_month - 24]
    fig = go.Figure()
    ends = []
    for line in selected_lines:
        m = shown[shown['line_name'] == line]
        if m.empty:
            continue
        # The month itself carries the hover in both views
        # (with the trend in all history).
        fig.add_trace(go.Scatter(
            x=m['month_start'], y=m['daily_avg'], name=line, mode='lines', legendgroup=line,
            line=dict(color=LINE_COLORS[line], width=1 if show_all else 2.5), opacity=0.35 if show_all else 1,
            customdata=np.stack([m['total'], m['trend']], axis=-1),
            hovertemplate=(f'{line}: %{{y:,.0f}} per day'
                           + (' · 12-month avg %{customdata[1]:,.0f}' if show_all
                              else ' · %{customdata[0]:,.0f} that month') + '<extra></extra>'),
        ))
        if show_all:
            trend = m.dropna(subset=['trend'])
            fig.add_trace(go.Scatter(
                x=trend['month_start'], y=trend['trend'], mode='lines', legendgroup=line, showlegend=False,
                line=dict(color=LINE_COLORS[line], width=2.5), hoverinfo='skip',
            ))
            if not trend.empty:
                ends.append((line, trend['month_start'].iloc[-1], trend['trend'].iloc[-1], line))
        else:
            last = m.iloc[-1]
            ends.append((line, last['month_start'], last['daily_avg'], line))
    top = shown['daily_avg'].max()
    label_line_ends(fig, ends, top)
    style(fig, height=360)
    # A fixed range: left to autorange, Plotly stretches the axis to fit the end
    # labels, which squeezes the lines on a phone. Ticks
    # spaced to stay legible there.
    first_month, last_month = shown['month_start'].min(), shown['month_start'].max()
    pad = (last_month - first_month) * 0.01
    fig.update_xaxes(range=[first_month - pad, last_month + pad],
                     tickformat='%Y' if show_all else '%b %Y', dtick='M36' if show_all else 'M12',
                     tick0=f'{latest_month.year}-01-01', gridcolor='rgba(0,0,0,0)', tickangle=0,
                     showspikes=True, spikemode='across', spikethickness=1, spikecolor=AXIS, spikedash='solid')
    count_axis(fig, top)
    rows = add_event_lines(fig, [(pd.Timestamp(when), *rest) for when, *rest in RIDERSHIP_EVENTS],
                           first_month, last_month) if show_all else 0
    # The end labels, names only, live in the right margin. No values: the 2
    # years' last month is the tiles' above, the trend isn't, and the hover
    # has both; a value would cost the plot a third of its width on a phone.
    fig.update_layout(margin=dict(l=4, r=84, t=13 + rows * EVENT_ROW_PX if rows else 8, b=4), hovermode='x unified')
    return fig


def daily_figure(first, last):
    """
    Entries every day from `first` to `last` (faint), under a centered 7-day
    average (bold) that evens out the weekday pattern, with EVENT_DAYS marked.
    Days without data (a fare-free line's) stay gaps.
    """
    span = pd.date_range(first, last)
    fig = go.Figure()
    ends = []
    for line in selected_lines:
        entries = (ridership[ridership['line_name'] == line].set_index('service_date')['gated_entries']
                   .reindex(span))
        if entries.isna().all():
            continue
        average = entries.rolling(7, center=True, min_periods=4).mean()
        fig.add_trace(go.Scatter(
            x=span, y=entries, name=line, mode='lines', connectgaps=False,
            line=dict(color=LINE_COLORS[line], width=1), opacity=0.35,
            customdata=average, hovertemplate=f'{line}: %{{y:,.0f}} · 7-day avg %{{customdata:,.0f}}<extra></extra>',
        ))
        fig.add_trace(go.Scatter(x=span, y=average, mode='lines', showlegend=False, hoverinfo='skip',
                                 line=dict(color=LINE_COLORS[line], width=2.5)))
        # A dot on each event day, at that day's entries, so the spike shows
        # even where a year of faint days blurs together on a phone.
        marked = EVENT_DAYS[EVENT_DAYS['date'].isin(entries.dropna().index)]
        fig.add_trace(go.Scatter(
            x=marked['date'], y=entries.reindex(marked['date']), mode='markers', showlegend=False,
            marker=dict(color=LINE_COLORS[line], size=8, line=dict(color=INK, width=1.5)),
            text=marked['label'], hovertemplate=f'%{{text}} · {line}: %{{y:,.0f}}<extra></extra>',
        ))
        end = average.last_valid_index()
        ends.append((line, end, average[end], line))
    top = ridership.loc[ridership['service_date'].between(first, last), 'gated_entries'].max()
    label_line_ends(fig, ends, top)
    style(fig, height=360)
    # Ticks spaced for phone width: months over a year or so, then years.
    days = (last - first).days
    tickformat, dtick = ('%b', 'M2') if days <= 366 else ('%b %Y', 'M6') if days <= 2 * 366 else (
        '%Y', 'M12' if days <= 6 * 366 else 'M24')
    pad = (last - first) * 0.01
    fig.update_xaxes(range=[first - pad, last + pad], tickformat=tickformat, dtick=dtick,
                     tick0=f'{first.year}-01-01', hoverformat='%a, %b %-d, %Y', gridcolor='rgba(0,0,0,0)',
                     tickangle=0, showspikes=True, spikemode='across', spikethickness=1, spikecolor=AXIS,
                     spikedash='solid')
    count_axis(fig, top)
    # Each event on the first row with room for it; labels near the span's
    # ends lean inward so they stay on the chart.
    events, row_ends = [], []
    if days <= EVENT_LABEL_MAX_DAYS:
        for when, short in EVENT_DAYS.loc[EVENT_DAYS['date'].between(first, last), ['date', 'short']].sort_values(
                'date').itertuples(index=False):
            row = next((r for r, end in enumerate(row_ends) if (when - end).days >= EVENT_GAP_SHARE * days),
                       len(row_ends))
            row_ends[row:row + 1] = [when]
            where = (when - first) / (last - first)
            events.append((when, short, 'left' if where < 0.25 else 'right' if where > 0.75 else 'center', 0, row))
    rows = add_event_lines(fig, events, first, last)
    fig.update_layout(margin=dict(l=4, r=84, t=13 + rows * EVENT_ROW_PX if rows else 8, b=4), hovermode='x unified')
    return fig


with st.container(key='card_monthly'):
    ridership_range = st.segmented_control(
        'Range', [RECENT_RANGE, ALL_RANGE, DAILY_RANGE], default=RECENT_RANGE,
        key='ridership_range', label_visibility='collapsed',
    ) or RECENT_RANGE  # Clicking the selected option clears it; fall back to the default
    if ridership_range == DAILY_RANGE:
        # Any run of whole months, the last 12 to start. The picker sits
        # outside the chart, so it can't trap page scrolling.
        months = pd.period_range(f'{archive_year}-01', ridership_through.to_period('M'), freq='M')
        month_labels = [f'{m:%b %Y}' for m in months]
        start_label, end_label = st.select_slider(
            'Months', month_labels, value=(month_labels[-12], month_labels[-1]), key='ridership_months',
            label_visibility='collapsed')
        first = months[month_labels.index(start_label)].start_time
        last = min(months[month_labels.index(end_label)].end_time.normalize(), ridership_through)
        through = f', through {ridership_through:%b %-d}' if last == ridership_through else ''
        card_title(f'Daily ridership, {start_label} – {end_label}' if start_label != end_label
                   else f'Daily ridership, {start_label}',
                   f'Entries each day (faint) and 7-day average (bold){through} · big days marked')
        show(daily_figure(first, last))
    else:
        show_all = ridership_range == ALL_RANGE
        card_title('Monthly ridership',
                   f'Average entries per day · each month (faint) and trailing 12 months (bold), since {archive_year}'
                   if show_all else 'Average entries per day · each month, last 2 years')
        show(monthly_figure(show_all))

# ── Days that moved ridership ─────────────────────────────────────────────────
# Each crowd and snow day in EVENT_DAYS against the same weekday in the weeks
# around it, in entries, not percent (helpers.day_vs_nearby says why).
with st.container(key='card_days'):
    card_title('Days that moved ridership',
               'Entries above or below the same weekday in the 4 weeks either side · holidays left out')
    # Days every selected line reported (a fare-free line's days are out).
    by_day = ridership.groupby('service_date')['gated_entries'].agg(['sum', 'count'])
    daily = by_day.loc[by_day['count'] == len(selected_lines), 'sum']
    holidays = ridership.loc[ridership['is_holiday'], 'service_date'].unique()
    snow = ridership.groupby('service_date')['snowfall_in'].first()
    days = EVENT_DAYS[EVENT_DAYS['kind'] != 'context']
    days = days.assign(change=day_vs_nearby(daily, days['date'], holidays).to_numpy(),
                       entries=daily.reindex(days['date']).to_numpy(),
                       snow=snow.reindex(days['date']).to_numpy()).dropna(subset=['change'])
    if days.empty:
        st.markdown('<div class="empty">None of these days are in the selected lines\' data.</div>',
                    unsafe_allow_html=True)
    else:
        # Biggest spikes on top, deepest drops at the bottom. Two-line names,
        # so labels stay short at phone width: what, then when (and how much
        # snow).
        days = days.sort_values('change', ascending=False)
        names = [f"{label}<br>{date:%b %-d, %Y}{f' · {inches:g}″ snow' if kind == 'snow' and inches > 0 else ''}"
                 for label, date, inches, kind in zip(days['label'], days['date'], days['snow'].fillna(0),
                                                      days['kind'], strict=True)]
        fig = go.Figure(go.Bar(
            x=days['change'], y=names, orientation='h',
            marker=dict(color=ACCENT, cornerradius=4),
            # A rise's label just past its bar's end; a drop's is drawn below,
            # by its base.
            text=[LABEL_GAP + fmt_count_change(n) if n > 0 else '' for n in days['change']],
            textposition='outside', outsidetextfont=dict(color=INK_2, size=11), constraintext='none',
            cliponaxis=False,
            hovertext=[f'{label}, {date:%a %b %-d, %Y}<br>{fmt_count(n)} entries · {fmt_count(n - c)} on an '
                       f'ordinary day ({fmt_count_change(c)})'
                       for label, date, n, c in zip(days['label'], days['date'], days['entries'], days['change'],
                                                    strict=True)],
            hoverinfo='text',
        ))
        # A drop's label just right of zero, beside its bar's base: past its
        # far end, it would need room the row names take at phone width.
        drops = days['change'] < 0
        fig.add_trace(go.Scatter(
            x=[0] * drops.sum(), y=[name for name, drop in zip(names, drops, strict=True) if drop], mode='text',
            text=[LABEL_GAP + fmt_count_change(n) for n in days.loc[drops, 'change']], textposition='middle right',
            textfont=dict(color=INK_2, size=11), hoverinfo='skip', showlegend=False, cliponaxis=False,
        ))
        style(fig, height=max(200, 44 * len(days) + 30))
        # 0 always in view. No tick labels: each bar carries its value, in a
        # fixed right margin when it runs past the plot.
        low, high = min(days['change'].min(), 0), max(days['change'].max(), 0)
        fig.update_xaxes(range=[low, high], showticklabels=False, showgrid=False, zeroline=True, zerolinecolor=AXIS,
                         zerolinewidth=1)
        fig.update_layout(margin_r=56)
        fig.update_yaxes(autorange='reversed', gridcolor='rgba(0,0,0,0)', tickfont=dict(color=INK_2, size=12))
        show(fig)
        # The records, named when the day is one of the days above. The
        # busiest month is a different thing: ordinary days were busiest in
        # 2014, but the record single days are later parades.
        record = daily.idxmax()
        named = dict(zip(days['date'], days['label'], strict=True)).get(record)
        by_month = monthly.groupby('month')['daily_avg'].agg(['sum', 'count'])
        month_totals = by_month.loc[by_month['count'] == len(selected_lines), 'sum']
        busiest_month = month_totals.idxmax()
        st.caption(f'Busiest day on record: {record:%a, %b %-d, %Y}' + (f', the {named}' if named else '')
                   + f', {fmt_count(daily[record])} entries. Busiest month: {busiest_month.strftime("%b %Y")}, '
                   f'{fmt_count(month_totals[busiest_month])} a day.')

impact_col, dow_col = st.columns(2, gap='medium')

# ── Ridership by alert effect ─────────────────────────────────────────────────
# Each line is compared only with its own calm days (gold's is_calm_day) in
# the same month, so seasons and the long trend cancel; calm days only, so a
# shutdown never lowers its own baseline (helpers.pct_vs_calm). The thresholds
# hold bars back until there's enough data to trust.
IMPACT_EFFECTS = ['Delay', 'Suspension', 'Shuttle']
MIN_CALM_DAYS = 4       # calm days a line needs in a month before that month's days can be scored
MIN_IMPACT_DAYS = 10    # scored days needed for a bar, both with the effect and calm

with impact_col:
    with st.container(key='card_impact'):
        # Only days since continuous alert tracking began can be called calm;
        # before that, a day with no alerts on record may just be missing data.
        tracking_day = coverage_start.tz_convert(TIMEZONE).tz_localize(None).normalize()
        impact_start = max(tracking_day, ridership_year_start)
        card_title('Ridership by alert effect',
                   ('Trailing 12 months' if impact_start == ridership_year_start
                    else f'Since continuous alert tracking began {fmt_day(coverage_start)}')
                   + ' · each line vs its own calm days in the same month')
        tracked = ordinary_days[ordinary_days['service_date'] >= impact_start]
        # Days that are neither calm nor one of IMPACT_EFFECTS (e.g. only a
        # service change) sit out of both sides of the comparison.
        tracked = tracked.assign(effect=tracked['most_severe_effect'], is_calm=tracked['is_calm_day'])
        tracked = tracked.assign(pct_vs_calm=pct_vs_calm(tracked, MIN_CALM_DAYS))
        impact = effect_vs_calm(tracked, IMPACT_EFFECTS, MIN_IMPACT_DAYS)
        waiting = [line for line in selected_lines if line not in set(impact['line_name'])]

        if impact.empty:
            st.markdown('<div class="empty">Too few calm days to compare.</div>', unsafe_allow_html=True)
        else:
            # Grouped by effect, lines in filter order within each group.
            impact = (impact.assign(effect_order=impact['effect'].map(IMPACT_EFFECTS.index),
                                    line_order=impact['line_name'].map(selected_lines.index))
                      .sort_values(['effect_order', 'line_order']))
            # One row per bar, plus a heading row (no bar) above each
            # effect's group. Headings sit flush left in the label column
            # and line names stay right-aligned against the axis, so lines
            # read as indented under them.
            impact['row'] = impact['effect'] + ' · ' + impact['line_name']
            rows, row_labels, headings = [], [], []
            for effect, group in impact.groupby('effect_order', sort=True):
                headings.append(IMPACT_EFFECTS[effect])
                rows += [IMPACT_EFFECTS[effect]] + list(group['row'])
                row_labels += [''] + list(group['line_name'])  # heading drawn as an annotation below
            label_width = 124  # px for the label column; fits "Suspension" and "Orange Line"
            fig = go.Figure(go.Bar(
                x=impact['pct'], y=impact['row'],
                orientation='h',
                marker=dict(color=[LINE_COLORS[line] for line in impact['line_name']], cornerradius=4),
                text=[LABEL_GAP + fmt_pct(p) + LABEL_GAP for p in impact['pct']], textposition='outside',
                constraintext='none',
                textfont=dict(color=INK_2, size=11), cliponaxis=False,
                hovertext=[f'{line} · {effect}: {fmt_pct(p)} vs calm days<br>{days} days · {calm} calm days'
                           for line, effect, p, days, calm in zip(impact['line_name'], impact['effect'], impact['pct'],
                                                                  impact['days'], impact['calm_days'], strict=True)],
                hoverinfo='text',
            ))
            style(fig, height=max(180, 30 * len(rows) + 30))
            # Axis fits the bars (0 always in view) with room past each end for
            # its label; a symmetric axis left too little room at phone width.
            low, high = min(impact['pct'].min(), 0), max(impact['pct'].max(), 0)
            pad = max(high - low, 4) * 0.8
            fig.update_xaxes(range=[low - pad, high + pad], ticksuffix='%', zeroline=True, zerolinecolor=AXIS,
                             zerolinewidth=1)
            # Fixed label column (not automargin) so headings
            # can be pinned to its left edge.
            fig.update_layout(margin_l=label_width)
            fig.update_yaxes(categoryorder='array', categoryarray=rows, tickvals=rows, ticktext=row_labels,
                             range=[len(rows) - 0.5, -0.5], gridcolor='rgba(0,0,0,0)', automargin=False,
                             tickfont=dict(color=INK_2, size=12))
            for heading in headings:
                fig.add_annotation(text=f'<b>{heading}</b>', x=0, xref='paper', xanchor='left',
                                   xshift=-label_width, y=heading, yref='y', showarrow=False,
                                   font=dict(color=INK, size=12))
            show(fig)
        st.caption("0% = that line's calm days. Shuttle riders and Green Line surface stops don't pass fare gates, "
                   "so these entries don't count them."
                   + (f" Too few calm days to compare: {', '.join(waiting)}." if waiting else ''))

# ── Day of week ───────────────────────────────────────────────────────────────
with dow_col:
    with st.container(key='card_dow'):
        card_title('Ridership by day of week', 'Trailing 12 months · average entries per day · holidays left out')
        # Average per weekday over the 12 months to the latest
        # published day, bars grouped by line. Holidays left out:
        # Monday holidays would pull Mondays down.
        recent = ordinary_days[ordinary_days['service_date'] >= ridership_year_start]
        dow = recent.groupby(['weekday', 'line_name'])['gated_entries'].mean().reset_index()
        fig = go.Figure()
        for line in selected_lines:
            d = dow[dow['line_name'] == line].sort_values('weekday')
            fig.add_trace(go.Bar(
                x=[WEEKDAYS[i][:3] for i in d['weekday']], y=d['gated_entries'], name=line,
                marker=dict(color=LINE_COLORS[line], cornerradius=4),
                hovertemplate=f'{line}<br>%{{x}}: %{{y:,.0f}} per day<extra></extra>',
            ))
        style(fig, height=280, legend=True)
        fig.update_layout(barmode='group', bargap=0.3, bargroupgap=0.12)
        count_axis(fig, dow['gated_entries'].max())
        fig.update_xaxes(gridcolor='rgba(0,0,0,0)', tickfont=dict(color=INK_2, size=12))
        show(fig)

# ══════════════════════════════════════════════════════════════════════════════
# 8. Weather
# ══════════════════════════════════════════════════════════════════════════════

section(
    'Weather',
    f"Every day since {ridership_all['service_date'].min():%b %Y}, as big storms are rare: each band's median day "
    'vs normal-weather days, on one scale.',
)

wx = ordinary_days.dropna(subset=['avg_temperature_f'])


def band_summary(df, column, bins, labels, baseline):
    """
    The median day's % vs typical per band of `column`, re-expressed relative
    to the `baseline` band (normal conditions), so the chart reads "heavy rain
    days run 3.6 points below dry days". Also returns the day count per band.

    The median, not the mean: when a line is shut for most of a month (the
    Orange Line around its 2022 shutdown), its "typical" for that month is
    near zero, and its open days score in the tens of thousands of percent,
    enough to swing a band's mean by tens of points; the median ignores them.
    """
    banded = df.assign(band=pd.cut(df[column], bins=bins, labels=labels))
    summary = (banded.groupby('band', observed=False)
               .agg(pct=('pct_vs_typical', 'median'), days=('service_date', 'nunique'))
               .reset_index().dropna(subset=['pct']))
    reference = summary.loc[summary['band'] == baseline, 'pct']
    summary['pct'] -= reference.iloc[0] if len(reference) else 0
    return summary


rain = band_summary(wx[wx['snowfall_in'].fillna(0) == 0], 'precipitation_in',
                    [-0.01, 0, 0.1, 0.5, 100], ['None', '≤ 0.1″', '0.1–0.5″', '0.5″+'], baseline='None')
winter = wx[wx['service_date'].dt.month.isin([12, 1, 2, 3])]
snow = band_summary(winter, 'snowfall_in', [-0.01, 0, 1, 4, 100], ['None', '≤ 1″', '1–4″', '4″+'], baseline='None')
temp = wx.assign(temp_vs_month=wx['avg_temperature_f'] - wx.groupby('month')['avg_temperature_f'].transform('mean'))
temps = band_summary(temp, 'temp_vs_month', [-100, -10, -5, 5, 10, 100],
                     ['≤ −10°', '−10 to −5°', '± 5°', '+5 to +10°', '≥ +10°'], baseline='± 5°')

# One scale across all three, so bar heights compare honestly: a big snowstorm
# really does move ridership far more than rain or temperature. Room past each
# end for the value labels.
all_pct = pd.concat([rain['pct'], snow['pct'], temps['pct']])
low, high = min(all_pct.min(), -2), max(all_pct.max(), 0)
weather_range = [low * 1.25, high + abs(low) * 0.2]

rain_col, snow_col, temp_col = st.columns(3, gap='medium')

with rain_col:
    with st.container(key='card_rain'):
        card_title('Rain', 'By daily rainfall · snow days are in the Snow chart')
        show(band_bars(rain, 'None', weather_range))
        st.caption('Inches of rain, as liquid')

with snow_col:
    with st.container(key='card_snow'):
        card_title('Snow', 'By daily snowfall · December–March')
        show(band_bars(snow, 'None', weather_range))
        st.caption('Inches of new snow, before melting')

with temp_col:
    with st.container(key='card_temp'):
        card_title('Temperature', "By degrees above or below the month's average")
        show(band_bars(temps, '± 5°', weather_range))
        st.caption('Degrees °F, on the daily mean: (high + low) / 2')

# ══════════════════════════════════════════════════════════════════════════════
# 9. Every mode
# ══════════════════════════════════════════════════════════════════════════════

# Riders on every mode, from the MBTA's monthly figures
# (gold.transit_ridership): they count boardings, a ride with a transfer
# counting twice, so they're never set beside the subway's gated entries (one
# source per view, decision 0018). Punctuality where the MBTA publishes it for
# every trip: commuter rail's reliability file and the ferry's trip legs
# (decision 0019); bus has none. The line buttons don't apply.

# The last 12 published months, against 2019, the last full year before the
# pandemic: twelve consecutive months hold each calendar month once, so the
# seasons match.
transit_latest = transit_all['month_start'].max()
transit_window = pd.date_range(end=transit_latest, periods=12, freq='MS')
transit_2019 = pd.date_range(f'{BASELINE_YEAR}-01-01', periods=12, freq='MS')
mode_now = riders_per_day_by_mode(transit_all, 'Total', transit_window).reindex(MODES)
mode_2019 = riders_per_day_by_mode(transit_all, 'Total', transit_2019).reindex(MODES)
transit_window_label = f'{transit_window[0]:%b %Y} – {transit_latest:%b %Y}'

section(
    'Every mode',
    f'{fmt_count(mode_now.sum())} boardings a day on every mode in the 12 months to {transit_latest:%b %Y}, '
    f"{mode_now.sum() / mode_2019.sum() * 100:.0f}% of {BASELINE_YEAR}. From the MBTA's monthly figures, which count "
    'every boarding (a ride with a transfer counts twice), so the subway runs higher here than in its gate entries '
    "above; commuter rail and ferry punctuality come from their own files. The line buttons don't apply.",
)

kpi_tiles([dict(label=mode, value=fmt_count(mode_now[mode]),
                sub=f'per{NBSP}day · {mode_now[mode] / mode_2019[mode] * 100:.0f}% of{NBSP}{BASELINE_YEAR}',
                color=MODE_COLORS[mode])
           for mode in MODES if pd.notna(mode_now[mode])], layout='thirds')

# ── Riders by mode, month by month ────────────────────────────────────────────
PER_DAY_VIEW, VS_2019_VIEW = 'Riders per day', f'% of {BASELINE_YEAR}'

with st.container(key='card_modes'):
    mode_view = st.segmented_control(
        'Measure', [PER_DAY_VIEW, VS_2019_VIEW], default=PER_DAY_VIEW,
        key='mode_view', label_visibility='collapsed',
    ) or PER_DAY_VIEW  # Clicking the selected option clears it; fall back to the default
    vs_2019 = mode_view == VS_2019_VIEW
    card_title('Riders by mode',
               f'Each month vs the same month in {BASELINE_YEAR}, so the seasons cancel'
               if vs_2019 else 'Boardings per day, each month')
    # Each mode's boardings per day, month by month.
    monthly_modes = (transit_all[transit_all['day_type'] == 'Total']
                     .groupby(['mode', 'month_start']).agg(riders=('riders_total', 'sum'), days=('day_count', 'max')))
    monthly_modes = (monthly_modes['riders'] / monthly_modes['days']).rename('per_day').reset_index()
    if vs_2019:
        same_month = monthly_modes[monthly_modes['month_start'].dt.year == BASELINE_YEAR].assign(
            calendar_month=lambda d: d['month_start'].dt.month).set_index(['mode', 'calendar_month'])['per_day']
        keys = pd.MultiIndex.from_arrays([monthly_modes['mode'], monthly_modes['month_start'].dt.month])
        monthly_modes['per_day'] = monthly_modes['per_day'] / same_month.reindex(keys).to_numpy() * 100
        # From the year after the baseline: 2019 against itself is a flat 100%.
        monthly_modes = monthly_modes[monthly_modes['month_start'].dt.year > BASELINE_YEAR]

    fig = go.Figure()
    ends = []
    for mode in MODES:
        m = monthly_modes[monthly_modes['mode'] == mode].dropna(subset=['per_day'])
        if m.empty:
            continue
        fig.add_trace(go.Scatter(
            x=m['month_start'], y=m['per_day'], name=mode, mode='lines',
            line=dict(color=MODE_COLORS[mode], width=2.5),
            hovertemplate=f'{mode}: %{{y:,.0f}}' + ('%' if vs_2019 else ' per day') + '<extra></extra>',
        ))
        ends.append((mode, m['month_start'].iloc[-1], m['per_day'].iloc[-1], mode))
    top = monthly_modes['per_day'].max()
    label_line_ends(fig, ends, top, colors=MODE_COLORS)
    style(fig, height=380)
    # End labels, names only, in a right margin wide enough for the longest.
    fig.update_layout(margin=dict(l=4, r=124, t=8, b=4), hovermode='x unified')
    first, last = monthly_modes['month_start'].min(), monthly_modes['month_start'].max()
    pad = (last - first) * 0.01
    # Every other year, so the labels fit beside the end labels at phone width.
    fig.update_xaxes(range=[first - pad, last + pad], tickformat='%Y', dtick='M24', tick0='2019-01-01',
                     gridcolor='rgba(0,0,0,0)', tickangle=0, showspikes=True, spikemode='across',
                     spikethickness=1, spikecolor=AXIS, spikedash='solid')
    if vs_2019:
        fig.update_yaxes(range=[0, top * 1.05], ticksuffix='%')
        fig.add_hline(y=100, line=dict(color=AXIS, width=1))
    else:
        count_axis(fig, top)
    show(fig)

weekend_col, ferry_col = st.columns(2, gap='medium')

# ── Weekdays and weekends against 2019 ────────────────────────────────────────
# Each mode's last 12 months by day type against 2019's.
DAY_TYPES = {'Weekday': ('Weekdays', 'circle', INK_2), 'Saturday': ('Saturdays', 'circle', ACCENT),
             'Sunday': ('Sundays', 'diamond', '#c4bdf5')}

with weekend_col:
    with st.container(key='card_weekends'):
        card_title('Weekdays and weekends',
                   f'{transit_window_label} vs {BASELINE_YEAR} · each mode by day of the week')
        fig = go.Figure()
        for day_type, (label, symbol, color) in DAY_TYPES.items():
            share = (riders_per_day_by_mode(transit_all, day_type, transit_window)
                     / riders_per_day_by_mode(transit_all, day_type, transit_2019) * 100).reindex(MODES).dropna()
            fig.add_trace(go.Scatter(
                x=share.values, y=share.index, mode='markers', name=label,
                marker=dict(symbol=symbol, size=11, color=color, line=dict(color=CARD, width=1.5)),
                hovertemplate=f'%{{y}} · {label}: %{{x:.0f}}% of {BASELINE_YEAR}<extra></extra>',
            ))
        style(fig, height=max(240, 40 * len(MODES) + 70), legend=True)
        fig.add_vline(x=100, line=dict(color=AXIS, width=1))
        fig.update_xaxes(ticksuffix='%', rangemode='tozero')
        fig.update_yaxes(autorange='reversed', gridcolor='rgba(0,0,0,0)', tickfont=dict(color=INK_2, size=12))
        show(fig)
        st.caption(f'100% = {BASELINE_YEAR}. Weekends came back further than weekdays on most modes: '
                   "the trips that didn't return are the commute. Commuter rail's weekend riders more than "
                   "doubled, a rise its operator, Keolis, reports too. The ferry's 2019 figures don't split "
                   'out weekends.')

# ── Ferries ───────────────────────────────────────────────────────────────────
# The last 12 months of trips the MBTA has published, route by route: riders,
# and how many departures left on time (no more than 5 minutes late, the
# MBTA's measure), which is nearly all of them on every route.
ferry_through = ferry_all['month_start'].max()
ferry_recent = ferry_all[ferry_all['month_start'] > ferry_through - pd.DateOffset(months=12)]
ferry_routes = ferry_recent.groupby('route_name')[['riders', 'service_days', 'measured_legs', 'on_time_legs']].sum()
ferry_window_label = f'{ferry_recent["month_start"].min():%b %Y} – {ferry_through:%b %Y}'

with ferry_col:
    with st.container(key='card_ferries'):
        card_title('Ferry riders by route',
                   f'Boardings per day it ran, {ferry_window_label} · seasonal routes over their season')
        per_day = (ferry_routes['riders'] / ferry_routes['service_days']).sort_values(ascending=False)
        show(ranked_bars(per_day.index.tolist(), per_day.tolist(), [fmt_count(n) for n in per_day],
                         [f'{route}<br>{n:,.0f} boardings per day it ran' for route, n in per_day.items()],
                         colors=MODE_COLORS['Ferry']))
        on_time = ferry_routes['on_time_legs'] / ferry_routes['measured_legs'] * 100
        st.caption(f'Departures on time, no more than 5 minutes late: {on_time.min():.1f}% '
                   f'({on_time.idxmin()}) to {on_time.max():.1f}% ({on_time.idxmax()}) by route.')

commuter_col, commuter_late_col = st.columns(2, gap='medium')

# ── Commuter rail, day by day ─────────────────────────────────────────────────
with commuter_col:
    with st.container(key='card_commuter_rail'):
        # The last 12 months the MBTA has published, by day of the week, with
        # federal holidays left out as in the subway's day-of-week chart.
        cr_daily = commuter_rail_all.groupby('service_date')['estimated_boardings'].sum()
        cr_through = cr_daily.index.max()
        cr_recent = cr_daily[cr_daily.index > cr_through - pd.DateOffset(months=12)]
        cr_holidays = USFederalHolidayCalendar().holidays(cr_recent.index.min(), cr_recent.index.max())
        cr_recent = cr_recent[~cr_recent.index.isin(cr_holidays)]
        by_weekday = cr_recent.groupby(cr_recent.index.day_of_week).mean().reindex(range(7))
        card_title('Commuter rail by day of the week',
                   f'Estimated boardings per day, 12 months to {cr_through:%b %-d, %Y} · holidays left out')
        fig = go.Figure(go.Bar(
            x=[WEEKDAYS[i][:3] for i in by_weekday.index], y=by_weekday.values,
            marker=dict(color=MODE_COLORS['Commuter Rail'], cornerradius=4),
            text=[fmt_count(n) for n in by_weekday.values], textposition='outside', cliponaxis=False,
            textfont=dict(color=INK_2, size=11),
            hovertemplate='%{x}: %{y:,.0f} boardings per day<extra></extra>',
        ))
        style(fig, height=280)
        count_axis(fig, by_weekday.max() * 1.15)
        fig.update_xaxes(gridcolor='rgba(0,0,0,0)', tickfont=dict(color=INK_2, size=12))
        show(fig)
        # The busiest day since the estimates began, named when it's one of
        # the days the subway's card measures.
        cr_record = cr_daily.idxmax()
        cr_named = dict(zip(EVENT_DAYS['date'], EVENT_DAYS['label'], strict=True)).get(cr_record)
        st.caption(f'Busiest day since the estimates began in {cr_daily.index.min():%b %Y}: '
                   f'{cr_record:%a, %b %-d, %Y}' + (f', the {cr_named}' if cr_named else '')
                   + f", {fmt_count(cr_daily[cr_record])} boardings. Estimates, which the MBTA doesn't guarantee.")

# ── Commuter rail trains late ─────────────────────────────────────────────────
# The last 12 months the MBTA has published, line by line. Late is a measured
# train not on time, by the MBTA's measure; canceled trains are counted apart.
cr_reliability_through = commuter_rail_reliability_all['service_date'].max()
cr_reliability_recent = commuter_rail_reliability_all[
    commuter_rail_reliability_all['service_date'] > cr_reliability_through - pd.DateOffset(months=12)]
cr_lines = cr_reliability_recent.groupby('line_name')[['trains_measured', 'trains_on_time', 'trains_canceled']].sum()

with commuter_late_col:
    with st.container(key='card_commuter_rail_late'):
        card_title('Commuter rail trains late',
                   f"Share of trains, 12 months to {cr_reliability_through:%b %-d, %Y} · the MBTA's on-time measure")
        late = (100 - cr_lines['trains_on_time'] / cr_lines['trains_measured'] * 100).sort_values(ascending=False)
        show(ranked_bars(late.index.tolist(), late.tolist(), [f'{p:.0f}%' for p in late],
                         [f"{line}<br>{p:.1f}% of {cr_lines.loc[line, 'trains_measured']:,} trains late · "
                          f"{cr_lines.loc[line, 'trains_canceled']:,} canceled" for line, p in late.items()],
                         colors=MODE_COLORS['Commuter Rail']))
        # Every line, a year at a time: 2019, and the last full year.
        cr_years = commuter_rail_reliability_all.groupby(commuter_rail_reliability_all['service_date'].dt.year)[
            ['trains_measured', 'trains_on_time']].sum()
        cr_late_by_year = 100 - cr_years['trains_on_time'] / cr_years['trains_measured'] * 100
        cr_last_full = cr_reliability_through.year - 1
        st.caption(f'Every line: {cr_late_by_year[BASELINE_YEAR]:.0f}% of trains late in {BASELINE_YEAR}, '
                   f'{cr_late_by_year[cr_last_full]:.0f}% in {cr_last_full}.')

# ══════════════════════════════════════════════════════════════════════════════
# 10. Footer
# ══════════════════════════════════════════════════════════════════════════════

st.markdown(f"""
<div class="footer">
  <b>Built by</b> · <a href="{GITHUB_URL}" target="_blank" rel="noopener">{AUTHOR}</a> ·
  <a href="{REPO_URL}" target="_blank" rel="noopener">Source code, decision records, and runbook on GitHub</a><br>
  <b>Stack</b> · Python ingest jobs on Cloud Run · BigQuery (bronze, silver, gold) · dbt Core · Terraform ·
  GitHub Actions · Streamlit<br>
  <b>Sources</b> · MBTA V3 API (alerts since Oct 2026, routes, stops, line shapes) · MBTA LAMP archive (the
  alerts the API's snapshots missed, from Sep 2019; topped up weekly) · MBTA Gated Station Entries (ArcGIS Open
  Data, with its yearly archive from 2014) · MBTA Monthly Ridership by Mode and Line, Commuter Rail Ridership by
  Service Date and Line, Ferry Daily Ridership by Trip, Heavy Rail Excess Trip Time, Commuter Rail Reliability,
  and Service Customer Satisfaction (ArcGIS Open Data) · NOAA GHCN-Daily, Boston Logan
  (USW00014739)<br>
  <b>Refresh</b> · Page data hourly, from alerts checked every 15 minutes · Weather daily
  (NOAA posts ~3 days behind) · Ridership, trip times, reliability, and the survey weekly (MBTA posts in batches,
  weeks to months behind)<br>
  <b>Incidents</b> · An incident groups the alerts the MBTA posts for one event (same route, cause, effect, and
  station, posted in close succession). Notices and facility issues (elevators, escalators, parking) are excluded.
  An alert ends at the end time the MBTA posted or when the MBTA closed it, whichever comes first; if the close
  wasn't seen, when it left the MBTA's feed.<br>
  <b>Delays riders feel</b> · Extra minutes per trip are the MBTA's estimates: each rider's trip, waiting and riding,
  against its baseline for that line, half hour, and direction, averaged over riders. The survey's positive share
  is its top three answers of seven (satisfied, or agreeing).<br>
  <b>Subway ridership</b> · Fare-gate entries on the four subway lines, as averages per day, weekends and holidays
  included. {BASELINE_YEAR} is the last full year before the pandemic. Days a line was fare-free (the Blue Line, Jul 5
  – Aug 4, 2024) are left out: with the gates open, entries didn't count riders. Days that moved ridership compare a
  day with the median of the same weekday in the four weeks either side, holidays left out, in entries rather than
  percent, since a percent would inflate recent days against lower ridership; the daily view's bold line is a centered
  7-day average, which evens out the weekdays.<br>
  <b>Every mode</b> · The MBTA's monthly figures count boardings, a ride with a transfer counting twice, on every mode
  alike, so modes are compared only with them, never with gated entries. {BASELINE_YEAR} comparisons set the last 12
  published months against all of {BASELINE_YEAR}, so the seasons match. Commuter rail boardings are the MBTA's daily
  estimates, and ferry riders count every trip leg. Punctuality is the MBTA's own measure: a ferry departure is late
  more than 5 minutes after schedule, and a commuter rail train's on time is from the MBTA's reliability file.<br>
  <b>Comparisons</b> · Like for like: same line and month, adjusted for day of week, with the ~10 federal holidays a
  year left out, since a holiday isn't a typical day. Durations and baselines are medians, so one shutdown can't skew
  them. Weather bars are the median day in each band vs normal-weather days. Alert-effect bars are the median day
  with that effect vs the line's calm days (no incident other than a station closure), each day counted under its
  most severe alert: shuttle buses, then a suspension, then a delay. A suspension may cover only part of a line or
  day. A bar needs {MIN_IMPACT_DAYS} days of the effect and {MIN_IMPACT_DAYS} calm days, in months with at least
  {MIN_CALM_DAYS} calm days.
</div>
""", unsafe_allow_html=True)
