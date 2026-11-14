{#
  gold.transit_ridership — one row per month × day type × service

  Monthly riders on every MBTA service, each grouped into its mode, for the
  dashboard's "Riding the MBTA" section. Only rows that don't overlap are
  kept: the published subtotals (Heavy Rail = Red + Orange + Blue, Light Rail
  = Green + Mattapan, All Bus = Bus + Silver Line + the retired private-carrier
  and trackless-trolley routes) would count riders twice. Day type Total stays
  beside Weekday, Saturday, and Sunday; a reader picks one or the other.

  Boardings, a ride with a transfer counting twice: compare modes with these
  figures only, never with gated entries (one source per view, decision 0018).

  Steps:
    1. final select — the services that don't overlap, each with its mode
#}

-- 1. Services that don't overlap, grouped into modes. A mode is named for what
--    it holds, so a chart's labels need no legend.
SELECT
    month_start,
    day_type,
    day_count,
    mode_or_line   AS service,
    CASE
        WHEN mode_or_line IN ('Red Line', 'Orange Line', 'Blue Line') THEN 'Red, Orange, Blue'
        WHEN mode_or_line IN ('Green Line', 'Mattapan Line') THEN 'Green, Mattapan'
        WHEN mode_or_line IN ('Bus', 'Silver Line', 'Private Bus', 'Trackless Trolley') THEN 'Bus, Silver Line'
        ELSE mode_or_line
    END            AS mode,
    riders_total,
    riders_per_day,
    ingested_at
FROM {{ ref('mbta_monthly_ridership__base') }}
WHERE mode_or_line NOT IN ('Heavy Rail', 'Light Rail', 'All Bus')
