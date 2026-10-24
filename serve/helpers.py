"""
Pure helpers for the dashboard — formatting, data freshness, incident shaping,
and the ridership-vs-calm-days comparison.

Kept out of app.py (which starts Streamlit when imported) so they can be unit
tested; see serve/tests/test_helpers.py.
"""

import html

import pandas as pd

# MBTA service dates and alert times are shown in Eastern time
TIMEZONE = "America/New_York"

# How old the alerts data can get before the header's status dot changes. Normally
# it's at most ~75 minutes old: gold rebuilds hourly and the page caches 15 minutes.
FRESH_HOURS = 2  # older: at least one hourly transform was missed
STALE_HOURS = 6  # older: the pipeline has been down for a while


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


def freshness(updated_at, now):
    """"fresh" · "late" · "stale": how far the alerts data has fallen behind its hourly refresh."""
    age_hours = (now - updated_at).total_seconds() / 3600
    if age_hours <= FRESH_HOURS:
        return "fresh"
    if age_hours <= STALE_HOURS:
        return "late"
    return "stale"


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


def pct_vs_calm(days, min_calm_days):
    """
    Each day's gated entries vs the median of its line's calm days on the same
    weekday, in percent (−20 = a fifth fewer entries than a calm day).

    `days` needs line_name, weekday, gated_entries, and is_calm (gold's
    is_calm_day: no incident other than a station closure that day).
    Comparing like weekdays removes the weekend pattern;
    pooling calm days only keeps shutdowns out of the baseline, however long
    they run. A line × weekday with fewer than `min_calm_days` calm days has
    no trustworthy baseline yet, so its days come back NaN.
    """
    calm = days[days["is_calm"]].groupby(["line_name", "weekday"])["gated_entries"]
    keys = pd.MultiIndex.from_frame(days[["line_name", "weekday"]])
    baseline = calm.median().where(calm.size() >= min_calm_days).reindex(keys).to_numpy()
    return (days["gated_entries"] / baseline - 1) * 100


def effect_vs_calm(days, effects, min_days):
    """
    Per line × effect: how far ridership on days with that effect ran from the
    line's calm days. Expects pct_vs_calm and effect (the day's most severe
    effect) columns. `pct` is re-expressed relative to the calm days' own
    average, so calm days sit at exactly 0%. A line × effect needs `min_days`
    scored days, and its line `min_days` scored calm days, to be reported.
    """
    scored = days.dropna(subset=["pct_vs_calm"])
    calm = scored[scored["is_calm"]].groupby("line_name")["pct_vs_calm"].agg(mean_calm="mean", size_calm="size")
    hit = (scored[scored["effect"].isin(effects)].groupby(["line_name", "effect"])["pct_vs_calm"]
           .agg(["mean", "size"]).reset_index())
    out = hit.join(calm, on="line_name")
    out = out[(out["size"] >= min_days) & (out["size_calm"] >= min_days)]
    return pd.DataFrame({
        "line_name": out["line_name"],
        "effect":    out["effect"],
        "pct":       ((1 + out["mean"] / 100) / (1 + out["mean_calm"] / 100) - 1) * 100,
        "days":      out["size"],
        "calm_days": out["size_calm"],
    }).reset_index(drop=True)


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
