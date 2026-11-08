"""
Pure helpers for the dashboard — formatting, data freshness, incident shaping
(which are active, one row per incident, hours covered per year), the
ridership-vs-calm-days comparison, chart label spacing, decoding the map's line
shapes, and choosing which affected stations the map names.

Kept out of app.py (which starts Streamlit when imported) so they can be unit
tested; see serve/tests/test_helpers.py.
"""

# Import standard libraries
import html

# Import third party libraries
import numpy as np
import pandas as pd

# MBTA service dates and alert times are shown in Eastern time
TIMEZONE = 'America/New_York'

# How old the alerts data can get before the header's status dot changes.
# Normally it's at most ~75 minutes old: gold rebuilds hourly and the page
# caches 15 minutes.
FRESH_HOURS = 2  # older: at least one hourly transform was missed
STALE_HOURS = 6  # older: the pipeline has been down for a while


def fmt_duration(minutes):
    """45 min · 2.7 hr · 1 day · 12 days"""
    if pd.isna(minutes) or minutes < 0:
        return '—'
    if minutes < 60:
        return f'{minutes:.0f} min'
    if minutes < 1440:
        return f'{minutes / 60:.1f} hr'
    days = minutes / 1440
    return '1 day' if days < 1.5 else f'{days:.0f} days'


def fmt_count(n):
    """1,284 · 118K · 3.2M"""
    if n >= 1_000_000:
        return f'{n / 1_000_000:.1f}M'
    if n >= 10_000:
        return f'{n / 1_000:.0f}K'
    return f'{n:,.0f}'


def fmt_pct(x, decimals=1):
    """Signed percent with a true minus sign: +2.1% · −6.4% · 0.0%"""
    if round(x, decimals) == 0:
        return f'{0:.{decimals}f}%'
    return f'{x:+.{decimals}f}%'.replace('-', '−')


def fmt_day(ts):
    """Oct 19"""
    return ts.tz_convert(TIMEZONE).strftime('%b %-d')


def freshness(updated_at, now):
    """"fresh" · "late" · "stale": how far the alerts data has fallen behind its hourly refresh."""
    age_hours = (now - updated_at).total_seconds() / 3600
    if age_hours <= FRESH_HOURS:
        return 'fresh'
    if age_hours <= STALE_HOURS:
        return 'late'
    return 'stale'


def esc(text):
    """HTML-escape a value for st.markdown cards; None or NaN becomes an empty string."""
    return html.escape(str(text)) if text is not None and not pd.isna(text) else ''


def strip_route_prefix(header):
    """MBTA headers repeat the route ("Green Line C Branch: ..."); the card already shows it."""
    head, sep, rest = str(header).partition(': ')
    return rest if sep and 'Line' in head and len(head) < 40 else header


def join_routes(route_names):
    """["Green Line B", "Green Line C"] → "Green Line B · C"; other lines joined with commas."""
    names = sorted(set(route_names))
    if len(names) > 1 and all(n.startswith('Green Line ') for n in names):
        return 'Green Line ' + ' · '.join(n.removeprefix('Green Line ') for n in names)
    return ', '.join(names)


def pct_vs_calm(days, min_calm_days):
    """
    Each day's gated entries vs its line's calm days in the same month, adjusted
    for the day of the week, in percent (−20 = a fifth fewer entries than a calm
    day would have had).

    `days` needs line_name, month, weekday, gated_entries, and is_calm (gold's
    is_calm_day, defined in gold/rail_ridership.sql).
      1. Weekday shape: each line's calm-day median per weekday, over all the
         days given, relative to its overall calm-day median. Dividing by it
         puts every day on a common weekday footing.
      2. Baseline: the line's median weekday-adjusted calm day in that month.
         Same month, so seasons and the long trend (the recovery, a line's
         slow decline) cancel; calm days only, so a shutdown, however long,
         never lowers its own baseline.
    A line × month with fewer than `min_calm_days` calm days, or a weekday with
    none, has no trustworthy baseline, so its days come back NaN.
    """
    calm = days[days['is_calm']]
    by_weekday = calm.groupby(['line_name', 'weekday'])['gated_entries'].median()
    shape = by_weekday / calm.groupby('line_name')['gated_entries'].median().reindex(
        by_weekday.index.get_level_values('line_name')).to_numpy()
    factor = shape.reindex(pd.MultiIndex.from_frame(days[['line_name', 'weekday']])).to_numpy()
    adjusted = days['gated_entries'] / factor

    calm_adjusted = adjusted[days['is_calm']].groupby([calm['line_name'], calm['month']])
    baseline = calm_adjusted.median().where(calm_adjusted.size() >= min_calm_days)
    baseline = baseline.reindex(pd.MultiIndex.from_frame(days[['line_name', 'month']])).to_numpy()
    return (adjusted / baseline - 1) * 100


def effect_vs_calm(days, effects, min_days):
    """
    Per line × effect: how far ridership on days with that effect ran from the
    line's calm days. Expects pct_vs_calm and effect (the day's most severe
    effect) columns. `pct` is the median scored day, re-expressed relative to
    the calm days' own median so calm days sit at exactly 0% (medians, so one
    odd day can't swing a bar). A line × effect needs `min_days` scored days,
    and its line `min_days` scored calm days, to be reported.
    """
    scored = days.dropna(subset=['pct_vs_calm'])
    calm = scored[scored['is_calm']].groupby('line_name')['pct_vs_calm'].agg(median_calm='median', size_calm='size')
    hit = (scored[scored['effect'].isin(effects)].groupby(['line_name', 'effect'])['pct_vs_calm']
           .agg(['median', 'size']).reset_index())
    out = hit.join(calm, on='line_name')
    out = out[(out['size'] >= min_days) & (out['size_calm'] >= min_days)]
    return pd.DataFrame({
        'line_name': out['line_name'],
        'effect':    out['effect'],
        'pct':       ((1 + out['median'] / 100) / (1 + out['median_calm'] / 100) - 1) * 100,
        'days':      out['size'],
        'calm_days': out['size_calm'],
    }).reset_index(drop=True)


def active_at(df, now):
    """Rows whose incident is in effect at `now`: started, and not yet ended (NULL end = ongoing)."""
    return df[(df['incident_start_at'] <= now)
              & (df['incident_end_at'].isna() | (df['incident_end_at'] >= now))]


def decode_polyline(encoded):
    """
    Google's encoded polyline format → [(lat, lon), ...], at its 5 decimal
    places. Each value is a variable-length delta from the point before it.
    """
    points, values, index = [], [0, 0], 0
    while index < len(encoded):
        for axis in range(2):
            shift, chunk = 0, 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                chunk |= (byte & 0x1f) << shift
                shift += 5
                if byte < 0x20:
                    break
            values[axis] += ~(chunk >> 1) if chunk & 1 else chunk >> 1
        points.append((values[0] / 1e5, values[1] / 1e5))
    return points


# Map text positions by compass direction: east first, then counterclockwise
COMPASS_TEXT_POSITIONS = ['middle right', 'top right', 'top center', 'top left',
                          'middle left', 'bottom left', 'bottom center', 'bottom right']


def run_end_labels(paths, stations, affected, default='top right', max_km=0.1):
    """
    Which of a line's affected stations to name, and where: only the ends of
    each run of consecutive affected stations, each name facing the way its run
    stops. A long shutdown reads by its ends (Kenmore … Government Center), and
    no name lands on the run's other stations. Returns {station_id: position}.

    paths     the line's shapes, each [(lat, lon), ...] along one branch
    stations  the line's stations: station_id, station_latitude, station_longitude
    affected  the affected station_ids

    Each path orders the stations within max_km of it by their nearest point
    (measured 2026-11-07: every station is within 75 m of its own line's path,
    and the nearest station of another branch 120 m off). A station ends a run
    where, on some path, the next station isn't affected, and its name faces
    that station; at a junction, that's down the branch the run doesn't take.
    A path's last station ends a run only if no other path runs through it
    (the B and C branches stop at Government Center; the run may not), and its
    name faces away from the run. A station beside a path it isn't on, such as
    Savin Hill beside the Braintree branch, counts as on it; at worst that names
    one more station. A station affected on its own, or on no path, is named
    at `default`.
    """
    lat = stations['station_latitude'].to_numpy(dtype=float)
    lon = stations['station_longitude'].to_numpy(dtype=float)
    ids = stations['station_id'].to_numpy()
    # Degrees to km, flat at a city's scale (a degree of longitude narrows with latitude)
    km_per_lat = 110.57
    km_per_lon = 111.32 * np.cos(np.radians(lat.mean())) if len(lat) else 0.0

    def facing(toward, away):
        angle = np.arctan2((lat[toward] - lat[away]) * km_per_lat, (lon[toward] - lon[away]) * km_per_lon)
        return COMPASS_TEXT_POSITIONS[round(angle / (np.pi / 4)) % 8]

    stops, path_ends, mid_run = {}, {}, set()
    for path in paths:
        points = np.asarray(path, dtype=float).reshape(-1, 2)
        if not len(points) or not len(lat):
            continue
        distances = np.hypot((lat[:, None] - points[:, 0]) * km_per_lat,
                             (lon[:, None] - points[:, 1]) * km_per_lon)
        nearest = distances.argmin(axis=1)
        on_path = np.flatnonzero(distances[np.arange(len(lat)), nearest] <= max_km)
        order = on_path[np.argsort(nearest[on_path], kind='stable')]
        hit = [ids[i] in affected for i in order]
        for k, i in enumerate(order):
            if not hit[k]:
                continue
            neighbors = [n for n in (k - 1, k + 1) if 0 <= n < len(order)]
            run = [order[n] for n in neighbors if hit[n]]
            stop = [order[n] for n in neighbors if not hit[n]]
            if len(run) == 2:
                mid_run.add(ids[i])
            elif run and stop:
                stops.setdefault(ids[i], facing(stop[0], i))
            elif run:
                path_ends.setdefault(ids[i], facing(i, run[0]))

    positions = {station_id: default for station_id in affected}
    for station_id in mid_run - set(stops):
        del positions[station_id]
    positions.update({station_id: position for station_id, position in path_ends.items()
                      if station_id not in mid_run})
    positions.update(stops)
    return positions


def spread_labels(positions, min_gap):
    """
    Nudge label positions (e.g. the y of each line's end label) apart so no two
    sit closer than `min_gap`, keeping their order and staying as close to
    where they started as the spacing allows. Returns positions in input order.
    """
    order = sorted(range(len(positions)), key=lambda i: positions[i])
    placed = [positions[i] for i in order]
    for k in range(1, len(placed)):
        placed[k] = max(placed[k], placed[k - 1] + min_gap)
    # Push the whole stack back down by half its overshoot, so labels spread
    # both ways around their marks rather than only upward
    overshoot = sum(p - positions[i] for p, i in zip(placed, order, strict=True)) / max(len(placed), 1)
    placed = [p - overshoot / 2 for p in placed]
    result = [0.0] * len(positions)
    for p, i in zip(placed, order, strict=True):
        result[i] = p
    return result


def hours_by_year(spans, now):
    """
    Hours per line per calendar year (Eastern) that at least one span covers,
    so spans overlapping on a line count once. `spans` needs line_name,
    start_at, and end_at (NaT = still going, so it ends now); spans that
    haven't started are skipped. A span is split at each New Year it crosses.
    """
    rows = []
    for line, group in spans.groupby('line_name'):
        ends = group['end_at'].fillna(now).clip(upper=now)
        merged = []
        for start, end in sorted(zip(group['start_at'], ends, strict=True)):
            if end <= start:
                continue
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        for start, end in merged:
            start, end = start.tz_convert(TIMEZONE), end.tz_convert(TIMEZONE)
            for year in range(start.year, end.year + 1):
                year_start = pd.Timestamp(year=year, month=1, day=1, tz=TIMEZONE)
                year_end = pd.Timestamp(year=year + 1, month=1, day=1, tz=TIMEZONE)
                hours = (min(end, year_end) - max(start, year_start)).total_seconds() / 3600
                rows.append((line, year, hours))
    by_year = pd.DataFrame(rows, columns=['line_name', 'year', 'hours'])
    return by_year.groupby(['line_name', 'year'], as_index=False)['hours'].sum()


def one_row_per_incident(df):
    """
    gold.rail_incidents has one row per incident × route, so a shutdown across
    four Green Line branches is four rows. Collapse to one row per incident with
    the routes joined ("Green Line B · C · D · E").
    """
    if df.empty:
        return df
    routes = df.groupby('incident_id')['route_name'].agg(join_routes)
    first = df.drop_duplicates('incident_id').set_index('incident_id')
    return first.assign(route_name=routes).reset_index()
