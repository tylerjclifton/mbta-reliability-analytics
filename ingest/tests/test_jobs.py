"""
Ingest job tests — each script, run against canned responses

Each test pins down part of a job's contract: what it requests, what reaches
bronze (one row per grain, the right types, the source's quirks handled), and
when it fails rather than load.
"""

# Import standard libraries
import datetime
import io
import json
import zipfile

# Import third party libraries
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

# ── lamp-alerts ───────────────────────────────────────────────────────────────

def lamp_file(table):
    """An Arrow table as the bytes of a LAMP parquet file."""
    buffer = io.BytesIO()
    pq.write_table(table, buffer)
    return buffer.getvalue()


def days_ago(days):
    """Epoch seconds, as LAMP's *_timestamp columns hold them."""
    return int((datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).timestamp())


def test_lamp_alerts_renames_columns_and_keeps_integers_nullable(run_job):
    df = run_job('lamp-alerts', [lamp_file(pa.table({
        'id': pa.array([1040505, 1040505], pa.int64()),
        'header_text.translation.text': ['Shuttle buses replace trains', 'Shuttle buses replace trains'],
        'closed_datetime': pa.array([datetime.datetime(2026, 10, 22, 12, 0), None], pa.timestamp('us')),
        'informed_entity.route_type': pa.array([2, None], pa.int8()),
        'last_modified_timestamp': pa.array([days_ago(1), days_ago(1)], pa.int64()),
    }))])

    assert list(df.columns) == ['id', 'header_text', 'closed_datetime', 'informed_entity_route_type',
                                'last_modified_timestamp']
    assert df['informed_entity_route_type'].dtype == 'Int64'
    assert df['informed_entity_route_type'].isna().tolist() == [False, True]


def test_lamp_alerts_loads_only_the_last_two_weeks(run_job):
    df = run_job('lamp-alerts', [lamp_file(pa.table({
        'id': pa.array([1, 2, 3], pa.int64()),
        'last_modified_timestamp': pa.array([days_ago(1), days_ago(13), days_ago(30)], pa.int64()),
    }))])

    assert df['id'].tolist() == [1, 2]


def test_lamp_alerts_window_can_reach_the_whole_file(run_job, monkeypatch):
    monkeypatch.setenv('LOOKBACK_DAYS', '4000')
    df = run_job('lamp-alerts', [lamp_file(pa.table({
        'id': pa.array([1, 2], pa.int64()),
        'last_modified_timestamp': pa.array([days_ago(1), days_ago(2000)], pa.int64()),
    }))])

    assert df['id'].tolist() == [1, 2]


def test_lamp_alerts_nothing_modified_in_the_window_fails_the_job(run_job):
    with pytest.raises(SystemExit) as exit_info:
        run_job('lamp-alerts', [lamp_file(pa.table({
            'id': pa.array([1], pa.int64()),
            'last_modified_timestamp': pa.array([days_ago(30)], pa.int64()),
        }))])

    assert exit_info.value.code == 1


def test_lamp_alerts_loads_every_batch(run_job):
    one_row_over_a_batch = pa.table({
        'id': pa.array(range(100_001), pa.int64()),
        'last_modified_timestamp': pa.array([days_ago(1)] * 100_001, pa.int64()),
    })

    run_job('lamp-alerts', [lamp_file(one_row_over_a_batch)])

    assert [len(df) for df in run_job.loads] == [100_000, 1]


def test_lamp_alerts_empty_file_fails_the_job(run_job):
    with pytest.raises(SystemExit) as exit_info:
        run_job('lamp-alerts', [lamp_file(pa.table({'id': pa.array([], pa.int64())}))])

    assert exit_info.value.code == 1


# ── mbta-alerts ───────────────────────────────────────────────────────────────

def alert(alert_id, routes, effect='DELAY', start='2026-10-21T08:00:00-04:00', end=None):
    """One alert in the MBTA V3 API's JSON:API shape."""
    return {
        'id': alert_id,
        'attributes': {
            'informed_entity': [{'route': r} for r in routes],
            'active_period': [{'start': start, 'end': end}],
            'effect': effect,
            'cause': 'DISABLED_TRAIN',
            'severity': 5,
            'header': 'Red Line: Delays of about 15 minutes',
            'description': None,
            'duration_certainty': 'ESTIMATED',
            'created_at': '2026-10-21T07:58:00-04:00',
            'updated_at': '2026-10-21T08:05:00-04:00',
        },
    }


def test_alerts_one_row_per_alert_kept_whole(run_job):
    """
    One row per alert — not per route — with nothing
    dropped (silver splits routes).
    """
    green = alert('1', ['Green-B', 'Green-C'])
    green['attributes']['informed_entity'][0]['stop'] = '70145'
    green['attributes']['active_period'].append({'start': '2026-10-28T08:00:00-04:00', 'end': None})

    raw = run_job('mbta-alerts', [{'data': [green, alert('2', ['Red'])]}])

    assert raw['alert_id'].tolist() == ['1', '2']
    assert json.loads(raw['alert_json'].iloc[0]) == green  # stops and every active period survive


def test_alerts_keep_every_effect_for_bronze(run_job):
    """
    Non-service effects (notices, elevators) are filtered in silver, not here.
    """
    raw = run_job('mbta-alerts', [{'data': [alert('1', ['Red'], effect='ELEVATOR_CLOSURE')]}])

    assert json.loads(raw['alert_json'].iloc[0])['attributes']['effect'] == 'ELEVATOR_CLOSURE'


def test_alerts_request_the_whole_feed(run_job, monkeypatch):
    """
    No route filter and every activity: every mode and effect
    reaches bronze (decision 0011).
    """
    monkeypatch.setenv('MBTA_API_KEY', 'test-key')
    bus = alert('1', ['39'])

    raw = run_job('mbta-alerts', [{'data': [bus]}])

    assert run_job.requests == [{
        'url': 'https://api-v3.mbta.com/alerts',
        'params': {'filter[activity]': 'ALL'},
        'headers': {'x-api-key': 'test-key'},
    }]
    assert raw['alert_id'].tolist() == ['1']  # a bus-only alert is kept, too


def test_alerts_empty_feed_writes_nothing(run_job):
    raw = run_job('mbta-alerts', [{'data': []}])

    assert raw.empty


# ── mbta-routes ───────────────────────────────────────────────────────────────

def test_routes_request_the_rail_routes_and_shape_one_row_each(run_job, monkeypatch):
    """
    The yearly job: asks for exactly the project's rail
    routes (common/mbta_api.py).
    """
    monkeypatch.delenv('MBTA_API_KEY', raising=False)
    red = {
        'id': 'Red',
        'attributes': {
            'long_name': 'Red Line', 'type': 1, 'color': 'DA291C', 'description': 'Rapid Transit',
            'direction_destinations': ['Ashmont/Braintree', 'Alewife'],
        },
    }

    rows = run_job('mbta-routes', [{'data': [red]}])

    assert run_job.requests == [{
        'url': 'https://api-v3.mbta.com/routes',
        'params': {'filter[id]': 'Red,Blue,Orange,Green-B,Green-C,Green-D,Green-E'},
        'headers': {},
    }]
    assert rows.to_dict('records') == [{
        'route_id': 'Red', 'long_name': 'Red Line', 'route_type': 1, 'color': 'DA291C',
        'description': 'Rapid Transit', 'direction_destinations': "['Ashmont/Braintree', 'Alewife']",
    }]


def test_routes_empty_response_fails_the_job(run_job):
    with pytest.raises(SystemExit) as exit_info:
        run_job('mbta-routes', [{'data': []}])

    assert exit_info.value.code == 1


# ── mbta-shapes ───────────────────────────────────────────────────────────────

def shapes_body(*shape_ids):
    """One route's shapes in the MBTA V3 API's JSON:API shape."""
    return {'data': [{'id': shape_id, 'attributes': {'polyline': f'encoded-{shape_id}'}} for shape_id in shape_ids]}


def test_shapes_request_each_rail_route_and_shape_one_row_per_shape(run_job, monkeypatch):
    monkeypatch.setenv('MBTA_API_KEY', 'test-key')
    # The API doesn't name the route, so each row takes the route requested.
    df = run_job('mbta-shapes', [shapes_body('canonical-931_0009', '931_0010')] + [shapes_body('x')] * 6)

    assert [request['params']['filter[route]'] for request in run_job.requests] == [
        'Red', 'Blue', 'Orange', 'Green-B', 'Green-C', 'Green-D', 'Green-E',
    ]
    assert run_job.requests[0] == {
        'url': 'https://api-v3.mbta.com/shapes',
        'params': {'filter[route]': 'Red'},
        'headers': {'x-api-key': 'test-key'},
    }
    assert df.iloc[:2].to_dict('records') == [
        {'route_id': 'Red', 'shape_id': 'canonical-931_0009', 'polyline': 'encoded-canonical-931_0009'},
        {'route_id': 'Red', 'shape_id': '931_0010', 'polyline': 'encoded-931_0010'},
    ]
    assert df['route_id'].nunique() == 7


def test_shapes_route_with_none_fails_before_anything_loads(run_job):
    """
    Silver reads only the latest run, so a partial snapshot would erase a line.
    """
    with pytest.raises(SystemExit) as exit_info:
        run_job('mbta-shapes', [shapes_body('x'), {'data': []}])

    assert exit_info.value.code == 1
    assert run_job.loads == []


# ── mbta-stops ────────────────────────────────────────────────────────────────

def stop(stop_id, name, location_type, parent=None, platform=None):
    """One stop in the MBTA V3 API's JSON:API shape."""
    return {
        'id': stop_id,
        'attributes': {'name': name, 'location_type': location_type, 'platform_name': platform,
                       'latitude': 42.35, 'longitude': -71.1, 'vehicle_type': None},
        'relationships': {'parent_station': {'data': {'id': parent, 'type': 'stop'} if parent else None}},
    }


def stops_body(stations, children):
    """
    A /stops response; the API leaves out "included" when there are no children.
    """
    return {'data': stations, 'included': children} if children else {'data': stations}


def test_stops_keep_stations_and_children_per_route(run_job):
    bu = stop('place-bucen', 'Boston University Central', 1)
    platform = stop('70145', 'Boston University Central', 0, parent='place-bucen', platform='Boston College')
    others = [stops_body([], [])] * 6  # the remaining six routes return nothing

    df = run_job('mbta-stops', [stops_body([bu], [platform])] + others)

    assert df['route_id'].tolist() == ['Red', 'Red']  # first route requested
    assert df['stop_id'].tolist() == ['place-bucen', '70145']
    assert pd.isna(df['parent_station_id'].iloc[0])  # stations have no parent
    assert df['parent_station_id'].iloc[1] == 'place-bucen'
    assert df['platform_name'].iloc[1] == 'Boston College'


def test_stops_request_each_rail_route_with_its_children(run_job, monkeypatch):
    monkeypatch.setenv('MBTA_API_KEY', 'test-key')

    run_job('mbta-stops', [stops_body([stop('place-x', 'X', 1)], [])] * 7)

    assert [request['params']['filter[route]'] for request in run_job.requests] == [
        'Red', 'Blue', 'Orange', 'Green-B', 'Green-C', 'Green-D', 'Green-E',
    ]
    assert run_job.requests[0] == {
        'url': 'https://api-v3.mbta.com/stops',
        'params': {'filter[route]': 'Red', 'include': 'child_stops'},
        'headers': {'x-api-key': 'test-key'},
    }


def test_stops_missing_enum_stays_null(run_job):
    df = run_job('mbta-stops', [stops_body([stop('place-x', 'X', 1)], [])] * 7)

    assert str(df['vehicle_type'].dtype) == 'Int64'
    assert df['vehicle_type'].isna().all()


def test_stops_empty_response_fails_the_job(run_job):
    with pytest.raises(SystemExit) as exit_info:
        run_job('mbta-stops', [stops_body([], [])] * 7)

    assert exit_info.value.code == 1


# ── mbta-ridership ────────────────────────────────────────────────────────────

def arcgis_page(rows, more):
    """One page of an ArcGIS statistics query."""
    return {
        'features': [{'attributes': {'service_date': ms, 'route_or_line': line, 'gated_entries': n}}
                     for ms, line, n in rows],
        'exceededTransferLimit': more,
    }


# Midnight Eastern on 2026-09-30, expressed (as ArcGIS does) in UTC epoch ms.
SEP_30_MS = int(datetime.datetime(2026, 9, 30, 4, tzinfo=datetime.timezone.utc).timestamp() * 1000)


def test_ridership_follows_pagination(run_job):
    df = run_job('mbta-ridership', [
        arcgis_page([(SEP_30_MS, 'Red Line', 136013.4)], more=True),
        arcgis_page([(SEP_30_MS, 'Blue Line', 40112.0)], more=False),
    ])

    assert sorted(df['route_or_line']) == ['Blue Line', 'Red Line']
    assert [request['params']['resultOffset'] for request in run_job.requests] == [0, 1]


def test_ridership_stops_paging_at_an_empty_page(run_job):
    """
    A page that adds nothing ends the loop, even if
    ArcGIS still says more remain.
    """
    df = run_job('mbta-ridership', [
        arcgis_page([(SEP_30_MS, 'Red Line', 136013.4)], more=True),
        arcgis_page([], more=True),
    ])

    assert len(run_job.requests) == 2
    assert df['route_or_line'].tolist() == ['Red Line']


def test_ridership_epoch_ms_becomes_service_date(run_job):
    df = run_job('mbta-ridership', [arcgis_page([(SEP_30_MS, 'Red Line', 1.5)], more=False)])

    assert df['service_date'].tolist() == [datetime.date(2026, 9, 30)]
    assert df['gated_entries'].dtype == float


def test_ridership_api_error_fails_the_job(run_job):
    with pytest.raises(SystemExit) as exit_info:
        run_job('mbta-ridership', [{'error': {'code': 400, 'message': 'bad query'}}])

    assert exit_info.value.code == 1


def test_ridership_empty_layer_fails_the_job(run_job):
    with pytest.raises(SystemExit) as exit_info:
        run_job('mbta-ridership', [arcgis_page([], more=False)])

    assert exit_info.value.code == 1


def archive_zip(files):
    """The yearly archive: a zip holding one CSV per year, keyed by path."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for path, csv_text in files.items():
            archive.writestr(path, csv_text)
    return buffer.getvalue()


def test_ridership_archive_sums_rail_days_before_the_layer(run_job, monkeypatch):
    monkeypatch.setenv('FROM_ARCHIVE', 'true')
    df = run_job('mbta-ridership', [archive_zip({
        'GSE_by_year/GSE_2019.csv': (
            'service_date,time_period,stop_id,station_name,route_or_line,gated_entries\n'
            '2019-02-05,"(07:00:00)",place-dwnxg,Downtown Crossing,Red Line,100.5\n'
            '2019-02-05,"(07:30:00)",place-dwnxg,Downtown Crossing,Red Line,50\n'
            '2019-02-05,"(07:00:00)",place-sstat,South Station,Silver Line,999\n'
        ),
        # Columns in another order, as in later years' files.
        'GSE_by_year/GSE_2024.csv': (
            'service_date,time_period,station_name,route_or_line,gated_entries,stop_id\n'
            '2024-09-30,"(08:00:00)",Airport,Blue Line,10,place-aport\n'
            '2024-10-01,"(08:00:00)",Airport,Blue Line,20,place-aport\n'
        ),
    })])

    assert df.sort_values('service_date').to_dict('records') == [
        {'service_date': datetime.date(2019, 2, 5), 'route_or_line': 'Red Line', 'gated_entries': 150.5},
        {'service_date': datetime.date(2024, 9, 30), 'route_or_line': 'Blue Line', 'gated_entries': 10.0},
    ]


def test_ridership_archive_without_older_days_fails_the_job(run_job, monkeypatch):
    monkeypatch.setenv('FROM_ARCHIVE', 'true')
    with pytest.raises(SystemExit) as exit_info:
        run_job('mbta-ridership', [archive_zip({
            'GSE_by_year/GSE_2025.csv': 'service_date,route_or_line,gated_entries\n2025-01-02,Red Line,5\n',
        })])

    assert exit_info.value.code == 1


# ── noaa-weather ──────────────────────────────────────────────────────────────

def ghcn_csv(rows):
    """
    A GHCN-Daily station CSV with the kept columns;
    values space-padded like NCEI's.
    """
    header = ('"DATE","TMAX","TMAX_ATTRIBUTES","TMIN","TMIN_ATTRIBUTES",'
              '"PRCP","PRCP_ATTRIBUTES","SNOW","SNOW_ATTRIBUTES"')
    lines = [header] + [
        f'"{d}","{tmax:>5}",",,1","{tmin:>5}",",,1","{prcp:>5}","{attrs}","{snow:>5}",",,1"'
        for d, tmax, tmin, prcp, attrs, snow in rows
    ]
    return '\n'.join(lines)


def test_weather_keeps_only_the_lookback_window(run_job, monkeypatch):
    monkeypatch.setenv('LOOKBACK_DAYS', '10')
    today = datetime.date.today()
    old, recent = today - datetime.timedelta(days=30), today - datetime.timedelta(days=3)

    df = run_job('noaa-weather', [ghcn_csv([
        (old, 100, 50, 0, ',,1,2400', 0),
        (recent, 167, 33, 0, 'T,,1,2400', 0),
    ])])

    assert df['observation_date'].tolist() == [recent]


def test_weather_empty_window_writes_nothing(run_job, monkeypatch):
    """
    NOAA running far behind isn't this job's failure; the
    freshness check catches a lasting gap.
    """
    monkeypatch.setenv('LOOKBACK_DAYS', '10')
    old = datetime.date.today() - datetime.timedelta(days=30)

    df = run_job('noaa-weather', [ghcn_csv([(old, 100, 50, 0, ',,1,2400', 0)])])

    assert df.empty


def test_weather_values_stay_in_source_units(run_job, monkeypatch):
    monkeypatch.setenv('LOOKBACK_DAYS', '10')
    day = datetime.date.today() - datetime.timedelta(days=2)

    df = run_job('noaa-weather', [ghcn_csv([(day, 167, -56, 119, ',,1,2400', 434)])])

    row = df.iloc[0]
    assert (row['tmax'], row['tmin'], row['prcp'], row['snow']) == (167, -56, 119, 434)
    assert row['prcp_attributes'] == ',,1,2400'
    assert str(df['tmax'].dtype) == 'Int64'  # nullable: missing values stay NULL


def test_weather_missing_value_is_null(run_job, monkeypatch):
    monkeypatch.setenv('LOOKBACK_DAYS', '10')
    day = datetime.date.today() - datetime.timedelta(days=2)
    # SNOW and its flags left empty, as NCEI writes a value it doesn't have.
    header = ghcn_csv([]).strip()
    row = f'"{day}","  167",",,1","   33",",,1","    0",",,1,2400","",""'

    df = run_job('noaa-weather', [header + '\n' + row])

    assert pd.isna(df['snow'].iloc[0])
