{#
  gold.commuter_rail_reliability — one row per service date × line × period

  Commuter rail trains measured, on time, and canceled, per day, line, and
  peak or off-peak period (decision 0019): each line's published rows (its
  branches) summed, so trains_on_time / trains_measured is the line's on-time
  share, the MBTA's measure. Totals, so the dashboard can add any span before
  dividing.

  Steps:
    1. final select — branches summed per line, named as the MBTA's daily
                      boardings name them (gold.commuter_rail_boardings)
#}

-- 1. Per day × line × period. Names follow the boardings file, but Franklin
--    and Foxboro stay apart, as the reliability file keeps them.
SELECT
    service_date,
    route_id,
    CASE route_id
        WHEN 'CR-Middleborough' THEN 'Middleborough/Lakeville'
        WHEN 'CR-NewBedford' THEN 'Fall River/New Bedford'
        WHEN 'CR-Newburyport' THEN 'Newburyport/Rockport'
        WHEN 'CR-Providence' THEN 'Providence/Stoughton'
        WHEN 'CR-Worcester' THEN 'Framingham/Worcester'
        WHEN 'CapeFlyer' THEN 'CapeFLYER'
        ELSE REGEXP_REPLACE(route_id, r'^CR-', '')
    END                         AS line_name,
    is_peak,
    SUM(trains_measured)        AS trains_measured,
    SUM(trains_on_time)         AS trains_on_time,
    SUM(trains_canceled)        AS trains_canceled,
    MAX(ingested_at)            AS ingested_at
FROM {{ ref('mbta_commuter_rail_reliability__base') }}
GROUP BY
    service_date,
    route_id,
    line_name,
    is_peak
