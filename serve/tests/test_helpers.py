"""
Tests for serve/helpers.py — dashboard formatting, incident shaping, and the
ridership-vs-calm-days comparison.
"""

import pandas as pd
import pytest

from helpers import (
    effect_vs_calm,
    fmt_count,
    fmt_duration,
    fmt_pct,
    join_routes,
    one_row_per_incident,
    pct_vs_calm,
    strip_route_prefix,
)


@pytest.mark.parametrize("minutes, expected", [
    (45, "45 min"),
    (156, "2.6 hr"),
    (1500, "1 day"),
    (20 * 1440, "20 days"),
    (None, "—"),
    (-5, "—"),
])
def test_fmt_duration(minutes, expected):
    assert fmt_duration(minutes) == expected


@pytest.mark.parametrize("n, expected", [(1284, "1,284"), (118_400, "118K"), (3_250_000, "3.2M")])
def test_fmt_count(n, expected):
    assert fmt_count(n) == expected


def test_fmt_pct_uses_a_true_minus_sign():
    assert fmt_pct(-6.42) == "−6.4%"
    assert fmt_pct(2.1) == "+2.1%"


def test_strip_route_prefix_only_strips_line_names():
    assert strip_route_prefix("Green Line C Branch: Trains are skipping Hawes St") == "Trains are skipping Hawes St"
    assert strip_route_prefix("Symphony station is closed") == "Symphony station is closed"
    assert strip_route_prefix("Notice: something") == "Notice: something"


def test_join_routes_compacts_green_line_branches():
    assert join_routes(["Green Line D", "Green Line B", "Green Line C"]) == "Green Line B · C · D"
    assert join_routes(["Red Line"]) == "Red Line"
    assert join_routes(["Red Line", "Orange Line"]) == "Orange Line, Red Line"


def test_one_row_per_incident_collapses_branches():
    df = pd.DataFrame({
        "incident_id": ["9", "9", "7"],
        "route_name": ["Green Line B", "Green Line C", "Red Line"],
        "incident_header": ["Shutdown", "Shutdown", "Delay"],
    })

    out = one_row_per_incident(df).set_index("incident_id")

    assert len(out) == 2
    assert out.loc["9", "route_name"] == "Green Line B · C"
    assert out.loc["7", "route_name"] == "Red Line"


def ridership_days(rows):
    """Line-days for the calm-day comparisons: (line, weekday, entries, effect or None)."""
    df = pd.DataFrame(rows, columns=["line_name", "weekday", "gated_entries", "effect"])
    return df.assign(is_calm=df["effect"].isna())


def test_pct_vs_calm_ignores_disrupted_days_in_the_baseline():
    # Calm Mondays at 100; the shutdown Mondays at 50 must not drag the baseline down
    df = ridership_days([("Red Line", 0, 100, None)] * 2 + [("Red Line", 0, 50, "Shuttle")] * 5)

    assert pct_vs_calm(df, min_calm_days=2).tolist() == [0, 0, -50, -50, -50, -50, -50]


def test_pct_vs_calm_compares_like_weekdays_and_lines():
    df = ridership_days([
        ("Red Line", 0, 100, None), ("Red Line", 0, 100, None),     # Monday baseline 100
        ("Red Line", 5, 40, None), ("Red Line", 5, 40, None),       # Saturday baseline 40
        ("Blue Line", 0, 20, None), ("Blue Line", 0, 20, None),     # Blue's own baseline 20
        ("Red Line", 5, 30, "Delay"), ("Blue Line", 0, 10, "Delay"),
    ])

    assert pct_vs_calm(df, min_calm_days=2).iloc[-2:].tolist() == [-25, -50]


def test_pct_vs_calm_needs_enough_calm_days():
    df = ridership_days([("Red Line", 0, 100, None), ("Red Line", 0, 60, "Shuttle")])

    assert pct_vs_calm(df, min_calm_days=2).isna().all()


def test_effect_vs_calm_reports_only_lines_with_enough_days():
    df = ridership_days(
        [("Red Line", 0, 100, None)] * 3 + [("Red Line", 0, 80, "Shuttle")] * 3
        + [("Blue Line", 0, 100, None)] * 3 + [("Blue Line", 0, 80, "Shuttle")] * 2  # too few shuttle days
    )
    df = df.assign(pct_vs_calm=pct_vs_calm(df, min_calm_days=3))

    out = effect_vs_calm(df, ["Shuttle"], min_days=3)

    assert out[["line_name", "effect", "days", "calm_days"]].values.tolist() == [["Red Line", "Shuttle", 3, 3]]
    assert out["pct"].iloc[0] == pytest.approx(-20)
