"""
Pure helpers for the dashboard — formatting and incident shaping.

Kept out of app.py (which starts Streamlit when imported) so they can be unit
tested; see serve/tests/test_helpers.py.
"""

import html

import pandas as pd

# MBTA service dates and alert times are shown in Eastern time
TIMEZONE = "America/New_York"


def fmt_duration(minutes):
    """45 min · 2.7 hr · 1 day · 12 days"""
    if pd.isna(minutes) or minutes < 0:
        return "—"
    if minutes < 60:
        return f"{minutes:.0f} min"
    if minutes < 1440:
        return f"{minutes / 60:.1f} hr"
    days = minutes / 1440
    return "1 day" if days < 1.5 else f"{days:.0f} days"


def fmt_count(n):
    """1,284 · 118K · 3.2M"""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n / 1_000:.0f}K"
    return f"{n:,.0f}"


def fmt_pct(x, decimals=1):
    """Signed percent with a true minus sign: +2.1% · −6.4%"""
    return f"{x:+.{decimals}f}%".replace("-", "−")


def fmt_day(ts):
    """Oct 19"""
    return ts.tz_convert(TIMEZONE).strftime("%b %-d")


def esc(text):
    return html.escape(str(text)) if text is not None and not pd.isna(text) else ""


def strip_route_prefix(header):
    """MBTA headers repeat the route ("Green Line C Branch: ..."); the card already shows it."""
    head, sep, rest = str(header).partition(": ")
    return rest if sep and "Line" in head and len(head) < 40 else header


def join_routes(route_names):
    """["Green Line B", "Green Line C"] → "Green Line B · C"; other lines joined with commas."""
    names = sorted(set(route_names))
    if len(names) > 1 and all(n.startswith("Green Line ") for n in names):
        return "Green Line " + " · ".join(n.removeprefix("Green Line ") for n in names)
    return ", ".join(names)


def one_row_per_incident(df):
    """
    gold.rail_incidents has one row per incident × route, so a shutdown across
    four Green Line branches is four rows. Collapse to one row per incident with
    the routes joined ("Green Line B · C · D · E").
    """
    if df.empty:
        return df
    routes = df.groupby("incident_id")["route_name"].agg(join_routes)
    first = df.drop_duplicates("incident_id").set_index("incident_id")
    return first.assign(route_name=routes).reset_index()
