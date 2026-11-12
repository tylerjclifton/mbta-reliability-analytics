{#
  gold.rail_incident_periods — one row per incident × route × alert period

  When each incident was actually in force, from its alerts' active periods
  (silver.mbta_alerts__by_period), for the views that care about the clock
  rather than the incident: hours out of service, which service days had a
  shuttle or suspension (gold.rail_ridership), and which incidents are in
  force right now or next. Planned work that posted several periods (each
  weekend of a month) has a row for each; most incidents have one.

  Service dates follow the MBTA's: a day runs from 3 AM to 3 AM, so a weekend
  diversion ending Monday at 2:59 AM covers Saturday and Sunday only
  (macros/service_date.sql).

  Steps:
    1. final select — each alert period with its incident, route, and line,
                      and the service dates it covers
#}

-- 1. Periods tagged with their incident (silver.mbta_alerts__grouped) and
--    line. A period still in force has no end, and no end date.
SELECT
    g.incident_id,
    p.route_id,
    r.route_name,
    r.line_name,
    g.alert_effect                                       AS incident_effect,
    p.alert_id,
    p.period_start_at,
    p.period_end_at,
    {{ service_date('p.period_start_at') }}              AS period_start_date,
    {{ service_date('p.period_end_at', is_end=true) }}   AS period_end_date
FROM {{ ref('mbta_alerts__by_period') }} AS p
INNER JOIN {{ ref('mbta_alerts__grouped') }} AS g
    ON
        p.alert_id = g.alert_id
        AND p.route_id = g.route_id
LEFT JOIN {{ ref('mbta_routes__base') }} AS r
    ON p.route_id = r.route_id
