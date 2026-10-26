"""
Ingest job tests: each script's shaping logic against canned API responses.

What each test pins down is the contract with bronze — one row per expected
grain, correct types, and the source's quirks (epoch timestamps, padded CSV
values, paginated responses) handled.
"""

import datetime
import json

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


def test_alerts_one_row_per_alert_kept_whole(run_job):
    """One row per alert — not per route — with nothing dropped (silver splits routes)."""
    green = alert("1", ["Green-B", "Green-C"])
    green["attributes"]["informed_entity"][0]["stop"] = "70145"
    green["attributes"]["active_period"].append({"start": "2026-10-28T08:00:00-04:00", "end": None})

    raw = run_job("mbta-alerts", [{"data": [green, alert("2", ["Red"])]}])

    assert raw["alert_id"].tolist() == ["1", "2"]
    assert json.loads(raw["alert_json"].iloc[0]) == green  # stops and every active period survive


def test_alerts_keep_every_effect_for_bronze(run_job):
    """Non-service effects (notices, elevators) are filtered in silver, not here."""
    raw = run_job("mbta-alerts", [{"data": [alert("1", ["Red"], effect="ELEVATOR_CLOSURE")]}])

    assert json.loads(raw["alert_json"].iloc[0])["attributes"]["effect"] == "ELEVATOR_CLOSURE"


def test_alerts_empty_feed_writes_nothing(run_job):
    raw = run_job("mbta-alerts", [{"data": []}])

    assert raw.empty


# ── mbta-stops ────────────────────────────────────────────────────────────────

def stop(stop_id, name, location_type, parent=None, platform=None):
    """One stop in the MBTA V3 API's JSON:API shape."""
    return {
        "id": stop_id,
        "attributes": {"name": name, "location_type": location_type, "platform_name": platform,
                       "latitude": 42.35, "longitude": -71.1, "vehicle_type": None},
        "relationships": {"parent_station": {"data": {"id": parent, "type": "stop"} if parent else None}},
    }


def stops_body(stations, children):
    return {"data": stations, "included": children}


def test_stops_keep_stations_and_children_per_route(run_job):
    bu = stop("place-bucen", "Boston University Central", 1)
    platform = stop("70145", "Boston University Central", 0, parent="place-bucen", platform="Boston College")
    others = [stops_body([], [])] * 6  # the remaining six routes return nothing

    df = run_job("mbta-stops", [stops_body([bu], [platform])] + others)

    assert df["route_id"].tolist() == ["Red", "Red"]  # first route requested
    assert df["stop_id"].tolist() == ["place-bucen", "70145"]
    assert pd.isna(df["parent_station_id"].iloc[0])  # stations have no parent
    assert df["parent_station_id"].iloc[1] == "place-bucen"
    assert df["platform_name"].iloc[1] == "Boston College"


def test_stops_missing_enum_stays_null(run_job):
    df = run_job("mbta-stops", [stops_body([stop("place-x", "X", 1)], [])] * 7)

    assert str(df["vehicle_type"].dtype) == "Int64"
    assert df["vehicle_type"].isna().all()


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
