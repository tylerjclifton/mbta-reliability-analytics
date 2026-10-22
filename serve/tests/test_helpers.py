"""
Tests for serve/helpers.py — dashboard formatting and incident shaping.
"""

import pandas as pd
import pytest

from helpers import fmt_count, fmt_duration, fmt_pct, join_routes, one_row_per_incident, strip_route_prefix


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
