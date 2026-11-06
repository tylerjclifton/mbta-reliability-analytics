"""
Tests for serve/helpers.py — dashboard formatting, data freshness, incident
shaping, the ridership-vs-calm-days comparison, hours covered per year, chart
label spacing, and decoding the map's line shapes.
"""

# Import third party libraries
import pandas as pd
import pytest

# Import the helpers under test
from helpers import (
    active_at,
    decode_polyline,
    effect_vs_calm,
    fmt_count,
    fmt_duration,
    fmt_pct,
    freshness,
    hours_by_year,
    join_routes,
    one_row_per_incident,
    pct_vs_calm,
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


def test_active_at_keeps_started_and_unended_incidents():
    now = pd.Timestamp('2026-10-20 12:00', tz='UTC')
    df = pd.DataFrame({
        'incident_id': ['ongoing', 'ends_later', 'ended', 'not_started'],
        'incident_start_at': pd.to_datetime(['2026-10-20 08:00', '2026-10-20 11:00',
                                             '2026-10-20 09:00', '2026-10-21 08:00'], utc=True),
        'incident_end_at': pd.to_datetime([None, '2026-10-20 13:00', '2026-10-20 10:00', None], utc=True),
    })

    assert active_at(df, now)['incident_id'].tolist() == ['ongoing', 'ends_later']


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
    # Calm Mondays at 100; the shutdown Mondays at 50 must not drag the baseline down
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
