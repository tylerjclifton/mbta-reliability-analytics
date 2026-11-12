"""
Dashboard helper tests — serve/helpers.py

Covers dashboard formatting, data freshness, incident shaping, the
ridership-vs-calm-days comparison, hours covered per year, chart label spacing,
decoding the map's line shapes, and naming affected stations.
"""

# Import third party libraries
import pandas as pd
import pytest

# Import the helpers under test
from helpers import (
    decode_polyline,
    effect_vs_calm,
    fmt_count,
    fmt_duration,
    fmt_pct,
    freshness,
    hours_by_year,
    in_force,
    join_routes,
    one_row_per_incident,
    pct_vs_calm,
    run_end_labels,
    spread_labels,
    strip_route_prefix,
)


@pytest.mark.parametrize('minutes, expected', [
    (45, '45 min'),
    (156, '2.6 hr'),
    (1500, '1 day'),
    (20 * 1440, '20 days'),
    (None, '—'),
    (-5, '—'),
])
def test_fmt_duration(minutes, expected):
    assert fmt_duration(minutes) == expected


@pytest.mark.parametrize('n, expected', [(1284, '1,284'), (118_400, '118K'), (3_250_000, '3.2M')])
def test_fmt_count(n, expected):
    assert fmt_count(n) == expected


@pytest.mark.parametrize('n, expected', [(8_310, '8.3K'), (707, '0.7K'), (14_200, '14K'), (40, '40'), (0, '0')])
def test_fmt_count_in_thousands_matches_a_k_axis(n, expected):
    assert fmt_count(n, thousands=True) == expected


def test_fmt_pct_uses_a_true_minus_sign():
    assert fmt_pct(-6.42) == '−6.4%'
    assert fmt_pct(2.1) == '+2.1%'


def test_fmt_pct_shows_zero_unsigned():
    assert fmt_pct(0) == '0.0%'
    assert fmt_pct(-0.04) == '0.0%'


@pytest.mark.parametrize('age_hours, expected', [
    (0.5, 'fresh'),
    (2, 'fresh'),    # boundary: a missed run or two is still on time
    (2.5, 'late'),
    (6, 'late'),
    (6.5, 'stale'),
    (48, 'stale'),
])
def test_freshness_by_age(age_hours, expected):
    now = pd.Timestamp('2026-10-23 22:00', tz='UTC')
    assert freshness(now - pd.Timedelta(hours=age_hours), now) == expected


def test_strip_route_prefix_only_strips_line_names():
    assert strip_route_prefix('Green Line C Branch: Trains are skipping Hawes St') == 'Trains are skipping Hawes St'
    assert strip_route_prefix('Symphony station is closed') == 'Symphony station is closed'
    assert strip_route_prefix('Notice: something') == 'Notice: something'


def test_join_routes_compacts_green_line_branches():
    assert join_routes(['Green Line D', 'Green Line B', 'Green Line C']) == 'Green Line B · C · D'
    assert join_routes(['Red Line']) == 'Red Line'
    assert join_routes(['Red Line', 'Orange Line']) == 'Orange Line, Red Line'


def in_force_inputs():
    """
    Five Red Line incidents at noon on Oct 20, and their alerts' periods.
    weekends posted Oct 17–19 and Oct 24–26: its own span is the first
    weekend (over), so the second stands in, next.
    """
    ts = lambda values: pd.to_datetime(values, utc=True)  # noqa: E731
    incidents = pd.DataFrame({
        'incident_id': ['ongoing', 'ends_later', 'ended', 'not_started', 'weekends'],
        'route_name': 'Red Line',
        'incident_start_at': ts(['2026-10-20 08:00', '2026-10-20 11:00', '2026-10-20 09:00',
                                 '2026-10-21 08:00', '2026-10-17 07:00']),
        'incident_end_at': ts([None, '2026-10-20 13:00', '2026-10-20 10:00', None, '2026-10-19 07:00']),
        'incident_duration_minutes': [240, 120, 60, None, 2880],
        'incident_header': ['a', 'b', 'c', 'd', 'Shuttles two weekends'],
    })
    periods = pd.DataFrame({
        'incident_id': ['ongoing', 'ends_later', 'ended', 'not_started', 'weekends', 'weekends'],
        'route_name': 'Red Line',
        'period_start_at': ts(['2026-10-20 08:00', '2026-10-20 11:00', '2026-10-20 09:00',
                               '2026-10-21 08:00', '2026-10-17 07:00', '2026-10-24 07:00']),
        'period_end_at': ts([None, '2026-10-20 13:00', '2026-10-20 10:00', None,
                             '2026-10-19 07:00', '2026-10-26 07:00']),
    })
    return incidents, periods


def test_in_force_keeps_incidents_running_or_to_come_on_their_own_span():
    incidents, periods = in_force_inputs()
    out = in_force(incidents, periods, pd.Timestamp('2026-10-20 12:00', tz='UTC')).set_index('incident_id')

    assert out[out['is_active']].index.tolist() == ['ongoing', 'ends_later']
    assert 'ended' not in out.index
    assert not out.loc['not_started', 'is_active']
    assert out.loc['ongoing', 'incident_duration_minutes'] == 240


def test_in_force_shows_a_later_period_on_its_own_dates():
    incidents, periods = in_force_inputs()

    # Between the weekends: the second is next, dated as itself.
    upcoming = in_force(incidents, periods, pd.Timestamp('2026-10-20 12:00', tz='UTC')).set_index('incident_id')
    assert not upcoming.loc['weekends', 'is_active']
    assert upcoming.loc['weekends', 'incident_start_at'] == pd.Timestamp('2026-10-24 07:00', tz='UTC')
    assert upcoming.loc['weekends', 'incident_duration_minutes'] == 2880
    assert upcoming.loc['weekends', 'incident_header'] == 'Shuttles two weekends'

    # During the second weekend: in force.
    during = in_force(incidents, periods, pd.Timestamp('2026-10-25 12:00', tz='UTC')).set_index('incident_id')
    assert during.loc['weekends', 'is_active']


def test_one_row_per_incident_collapses_branches():
    df = pd.DataFrame({
        'incident_id': ['9', '9', '7'],
        'route_name': ['Green Line B', 'Green Line C', 'Red Line'],
        'incident_header': ['Shutdown', 'Shutdown', 'Delay'],
    })

    out = one_row_per_incident(df).set_index('incident_id')

    assert len(out) == 2
    assert out.loc['9', 'route_name'] == 'Green Line B · C'
    assert out.loc['7', 'route_name'] == 'Red Line'


def ridership_days(rows):
    """
    Line-days for the calm-day comparisons: (line, weekday, entries, effect or
    None[, month]); the month defaults to January 2026.
    """
    rows = [row if len(row) == 5 else (*row, '2026-01') for row in rows]
    df = pd.DataFrame(rows, columns=['line_name', 'weekday', 'gated_entries', 'effect', 'month'])
    return df.assign(is_calm=df['effect'].isna(), month=pd.PeriodIndex(df['month'], freq='M'))


def test_pct_vs_calm_ignores_disrupted_days_in_the_baseline():
    # Calm Mondays at 100; the shutdown Mondays at 50
    # must not drag the baseline down.
    df = ridership_days([('Red Line', 0, 100, None)] * 2 + [('Red Line', 0, 50, 'Shuttle')] * 5)

    assert pct_vs_calm(df, min_calm_days=2).tolist() == [0, 0, -50, -50, -50, -50, -50]


def test_pct_vs_calm_compares_like_weekdays_and_lines():
    df = ridership_days([
        ('Red Line', 0, 100, None), ('Red Line', 0, 100, None),     # Monday baseline 100
        ('Red Line', 5, 40, None), ('Red Line', 5, 40, None),       # Saturday baseline 40
        ('Blue Line', 0, 20, None), ('Blue Line', 0, 20, None),     # Blue's own baseline 20
        ('Red Line', 5, 30, 'Delay'), ('Blue Line', 0, 10, 'Delay'),
    ])

    assert pct_vs_calm(df, min_calm_days=2).iloc[-2:].tolist() == [-25, -50]


def test_pct_vs_calm_compares_within_the_month():
    # Ridership doubled from January to February (a trend, or the seasons). A
    # February shuttle day at 180 is 10% below February's calm days, though
    # it's above the calm days pooled across both months.
    df = ridership_days([
        ('Red Line', 0, 100, None, '2026-01'), ('Red Line', 0, 100, None, '2026-01'),
        ('Red Line', 0, 200, None, '2026-02'), ('Red Line', 0, 200, None, '2026-02'),
        ('Red Line', 0, 180, 'Shuttle', '2026-02'),
    ])

    assert pct_vs_calm(df, min_calm_days=2).iloc[-1] == pytest.approx(-10)


def test_pct_vs_calm_needs_enough_calm_days():
    df = ridership_days([('Red Line', 0, 100, None), ('Red Line', 0, 60, 'Shuttle')])

    assert pct_vs_calm(df, min_calm_days=2).isna().all()


def test_effect_vs_calm_reports_only_lines_with_enough_days():
    df = ridership_days(
        [('Red Line', 0, 100, None)] * 3 + [('Red Line', 0, 80, 'Shuttle')] * 3
        + [('Blue Line', 0, 100, None)] * 3 + [('Blue Line', 0, 80, 'Shuttle')] * 2  # too few shuttle days
    )
    df = df.assign(pct_vs_calm=pct_vs_calm(df, min_calm_days=3))

    out = effect_vs_calm(df, ['Shuttle'], min_days=3)

    assert out[['line_name', 'effect', 'days', 'calm_days']].values.tolist() == [['Red Line', 'Shuttle', 3, 3]]
    assert out['pct'].iloc[0] == pytest.approx(-20)


def span(line, start, end):
    """One span for hours_by_year, times in Eastern."""
    return {'line_name': line, 'start_at': pd.Timestamp(start, tz='America/New_York'),
            'end_at': pd.Timestamp(end, tz='America/New_York') if end else pd.NaT}


NOW = pd.Timestamp('2026-06-01 12:00', tz='America/New_York')


def test_hours_by_year_counts_overlapping_spans_once_per_line():
    spans = pd.DataFrame([
        span('Green Line', '2025-03-01 10:00', '2025-03-01 14:00'),   # e.g. the B branch
        span('Green Line', '2025-03-01 12:00', '2025-03-01 16:00'),   # the C branch, overlapping
        span('Red Line', '2025-03-01 12:00', '2025-03-01 13:00'),
    ])
    out = hours_by_year(spans, NOW).set_index('line_name')['hours']
    assert out.to_dict() == {'Green Line': 6.0, 'Red Line': 1.0}


def test_hours_by_year_splits_a_span_at_new_year():
    out = hours_by_year(pd.DataFrame([span('Red Line', '2024-12-31 22:00', '2025-01-01 03:00')]), NOW)
    assert out.set_index('year')['hours'].to_dict() == {2024: 2.0, 2025: 3.0}


def test_hours_by_year_ends_ongoing_spans_now_and_skips_future_ones():
    spans = pd.DataFrame([
        span('Red Line', '2026-06-01 10:00', None),                     # still going
        span('Red Line', '2026-07-01 09:00', '2026-07-01 17:00'),       # planned
    ])
    assert hours_by_year(spans, NOW)['hours'].tolist() == [2.0]


def test_decode_polyline_matches_googles_published_example():
    assert decode_polyline('_p~iF~ps|U_ulLnnqC_mqNvxq`@') == [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]


def test_decode_polyline_handles_an_empty_path():
    assert decode_polyline('') == []


def test_spread_labels_keeps_order_and_minimum_gap():
    out = spread_labels([83, 79, 64, 70], min_gap=7)
    assert sorted(out, reverse=True) == [out[0], out[1], out[3], out[2]]   # order kept
    gaps = sorted(out)
    assert all(b - a >= 7 - 1e-9 for a, b in zip(gaps, gaps[1:], strict=False))


def test_spread_labels_leaves_well_spaced_labels_alone():
    assert spread_labels([10, 30, 50], min_gap=7) == [10, 30, 50]


def stations_at(**coords):
    """gold.rail_stations rows for one line, from station_id=(lat, lon)."""
    return pd.DataFrame([{'station_id': s, 'station_latitude': lat, 'station_longitude': lon}
                         for s, (lat, lon) in coords.items()])


# Five stations ~0.8 km apart on an east–west line, and its path.
WEST_EAST = stations_at(A=(42.35, -71.10), B=(42.35, -71.09), C=(42.35, -71.08), D=(42.35, -71.07), E=(42.35, -71.06))
WEST_EAST_PATH = [(42.35, -71.10 + i / 1000) for i in range(41)]


def test_run_end_labels_names_only_the_ends_facing_where_the_run_stops():
    labels = run_end_labels([WEST_EAST_PATH], WEST_EAST, {'B', 'C', 'D'})
    assert labels == {'B': 'middle left', 'D': 'middle right'}


def test_run_end_labels_faces_a_run_at_the_end_of_the_line_away_from_it():
    assert run_end_labels([WEST_EAST_PATH], WEST_EAST, {'D', 'E'}) == {'D': 'middle left', 'E': 'middle right'}


def test_run_end_labels_names_a_lone_station_at_the_default():
    assert run_end_labels([WEST_EAST_PATH], WEST_EAST, {'B', 'D'}) == {'B': 'top right', 'D': 'top right'}


def test_run_end_labels_names_a_junction_facing_down_the_branch_the_run_skips():
    # A trunk A–B–C, then one branch east to D and one north to N; the run
    # continues east, so C faces north, where the run stops.
    stations = stations_at(A=(42.35, -71.10), B=(42.35, -71.09), C=(42.35, -71.08),
                           D=(42.35, -71.07), N=(42.36, -71.08))
    east = [(42.35, -71.10 + i / 1000) for i in range(31)]
    north = [(42.35, -71.10 + i / 1000) for i in range(21)] + [(42.35 + i / 1000, -71.08) for i in range(1, 11)]
    labels = run_end_labels([east, north], stations, {'B', 'C', 'D'})
    assert labels == {'B': 'middle left', 'C': 'top center', 'D': 'middle right'}


def test_run_end_labels_ignores_a_branch_ending_mid_run():
    # Like the B and C branches at Government Center: one path stops at C, the
    # other carries the run on to D, so C isn't an end.
    short = [(42.35, -71.10 + i / 1000) for i in range(21)]
    labels = run_end_labels([WEST_EAST_PATH, short], WEST_EAST, {'B', 'C', 'D'})
    assert labels == {'B': 'middle left', 'D': 'middle right'}


def test_run_end_labels_names_a_station_on_no_path_at_the_default():
    stations = stations_at(A=(42.35, -71.10), Z=(42.40, -71.10))
    assert run_end_labels([WEST_EAST_PATH], stations, {'Z'}) == {'Z': 'top right'}
