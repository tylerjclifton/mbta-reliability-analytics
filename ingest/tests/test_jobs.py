"""
Ingest job tests: each script's shaping logic against canned API responses.

What each test pins down is the contract with bronze — one row per expected
grain, correct types, and the source's quirks (epoch timestamps, padded CSV
values, paginated responses) handled.
"""

import datetime

import pandas as pd
import pytest

# ── mbta-alerts ───────────────────────────────────────────────────────────────

def alert(alert_id, routes, effect="DELAY", start="2026-10-21T08:00:00-04:00", end=None):
    """One alert in the MBTA V3 API's JSON:API shape."""
    return {
        "id": alert_id,
        "attributes": {
            "informed_entity": [{"route": r} for r in routes],
            "active_period": [{"start": start, "end": end}],
            "effect": effect,
            "cause": "DISABLED_TRAIN",
            "severity": 5,
            "header": "Red Line: Delays of about 15 minutes",
            "description": None,
            "duration_certainty": "ESTIMATED",
            "created_at": "2026-10-21T07:58:00-04:00",
            "updated_at": "2026-10-21T08:05:00-04:00",
        },
    }


def test_alerts_one_row_per_rail_route(run_job):
    df = run_job("mbta-alerts", [{"data": [
        # Green Line alert listed per branch, with a duplicate entity and a bus route
        alert("1", ["Green-C", "Green-B", "Green-B", "39"]),
        alert("2", ["Red"]),
    ]}])

    assert sorted(zip(df["alert_id"], df["route"], strict=True)) == [("1", "Green-B"), ("1", "Green-C"), ("2", "Red")]


def test_alerts_keep_every_effect_for_bronze(run_job):
    """Non-service effects (notices, elevators) are filtered in silver, not here."""
    df = run_job("mbta-alerts", [{"data": [alert("1", ["Red"], effect="ELEVATOR_CLOSURE")]}])

    assert df["effect"].tolist() == ["ELEVATOR_CLOSURE"]


def test_alerts_parse_timestamps_and_missing_end(run_job):
    df = run_job("mbta-alerts", [{"data": [alert("1", ["Red"], end=None)]}])

    start = df["active_period_start"].iloc[0]
    assert start == datetime.datetime(2026, 10, 21, 12, 0, tzinfo=datetime.timezone.utc)
    assert df["active_period_end"].iloc[0] is None


def test_alerts_empty_feed_writes_nothing(run_job):
    df = run_job("mbta-alerts", [{"data": []}])

    assert df.empty


# ── mbta-ridership ────────────────────────────────────────────────────────────

def arcgis_page(rows, more):
    """One page of an ArcGIS statistics query."""
    return {
        "features": [{"attributes": {"service_date": ms, "route_or_line": line, "gated_entries": n}}
                     for ms, line, n in rows],
        "exceededTransferLimit": more,
    }


# Midnight Eastern on 2026-09-30, expressed (as ArcGIS does) in UTC epoch ms
SEP_30_MS = int(datetime.datetime(2026, 9, 30, 4, tzinfo=datetime.timezone.utc).timestamp() * 1000)


def test_ridership_follows_pagination(run_job):
    df = run_job("mbta-ridership", [
        arcgis_page([(SEP_30_MS, "Red Line", 136013.4)], more=True),
        arcgis_page([(SEP_30_MS, "Blue Line", 40112.0)], more=False),
    ])

    assert sorted(df["route_or_line"]) == ["Blue Line", "Red Line"]


def test_ridership_epoch_ms_becomes_service_date(run_job):
    df = run_job("mbta-ridership", [arcgis_page([(SEP_30_MS, "Red Line", 1.5)], more=False)])

    assert df["service_date"].tolist() == [datetime.date(2026, 9, 30)]
    assert df["gated_entries"].dtype == float


def test_ridership_api_error_fails_the_job(run_job):
    with pytest.raises(SystemExit) as exit_info:
        run_job("mbta-ridership", [{"error": {"code": 400, "message": "bad query"}}])

    assert exit_info.value.code == 1


# ── noaa-weather ──────────────────────────────────────────────────────────────

def ghcn_csv(rows):
    """A GHCN-Daily station CSV with the kept columns; values space-padded like NCEI's."""
    header = ('"DATE","TMAX","TMAX_ATTRIBUTES","TMIN","TMIN_ATTRIBUTES",'
              '"PRCP","PRCP_ATTRIBUTES","SNOW","SNOW_ATTRIBUTES"')
    lines = [header] + [
        f'"{d}","{tmax:>5}",",,1","{tmin:>5}",",,1","{prcp:>5}","{attrs}","{snow:>5}",",,1"'
        for d, tmax, tmin, prcp, attrs, snow in rows
    ]
    return "\n".join(lines)


def test_weather_keeps_only_the_lookback_window(run_job, monkeypatch):
    monkeypatch.setenv("LOOKBACK_DAYS", "10")
    today = datetime.date.today()
    old, recent = today - datetime.timedelta(days=30), today - datetime.timedelta(days=3)

    df = run_job("noaa-weather", [ghcn_csv([
        (old, 100, 50, 0, ",,1,2400", 0),
        (recent, 167, 33, 0, "T,,1,2400", 0),
    ])])

    assert df["observation_date"].tolist() == [recent]


def test_weather_values_stay_in_source_units(run_job, monkeypatch):
    monkeypatch.setenv("LOOKBACK_DAYS", "10")
    day = datetime.date.today() - datetime.timedelta(days=2)

    df = run_job("noaa-weather", [ghcn_csv([(day, 167, -56, 119, ",,1,2400", 434)])])

    row = df.iloc[0]
    assert (row["tmax"], row["tmin"], row["prcp"], row["snow"]) == (167, -56, 119, 434)
    assert row["prcp_attributes"] == ",,1,2400"
    assert str(df["tmax"].dtype) == "Int64"  # nullable: missing values stay NULL


def test_weather_missing_value_is_null(run_job, monkeypatch):
    monkeypatch.setenv("LOOKBACK_DAYS", "10")
    day = datetime.date.today() - datetime.timedelta(days=2)
    # SNOW and its flags left empty, as NCEI writes a value it doesn't have
    header = ghcn_csv([]).strip()
    row = f'"{day}","  167",",,1","   33",",,1","    0",",,1,2400","",""'

    df = run_job("noaa-weather", [header + "\n" + row])

    assert pd.isna(df["snow"].iloc[0])
