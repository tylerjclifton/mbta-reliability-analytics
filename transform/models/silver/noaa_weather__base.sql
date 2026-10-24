{#
  silver.noaa_weather__base — one row per observation date

  Latest GHCN-Daily values for Boston Logan, quality-checked and converted
  from NOAA's metric source units to US units.

  Steps:
    1. latest_versions — latest pull per observation date (NOAA revises recent days)
    2. quality_checked — NULL out any value NOAA's quality control flagged
    3. final select    — convert units: tenths of °C → °F, tenths of mm → in,
                         mm → in
#}

WITH

    -- 1. Latest pull per observation date
    latest_versions AS (
        SELECT *
        FROM {{ source('bronze', 'noaa_weather') }}
        {{ keep_latest_version(['station_id', 'observation_date']) }}
    ),

    -- 2. Keep only values that passed NOAA quality control; source units retained
    quality_checked AS (
        SELECT
            station_id,
            observation_date,
            {{ null_if_failed_ghcn_qc('tmax') }}                AS tmax_tenths_c,
            {{ null_if_failed_ghcn_qc('tmin') }}                AS tmin_tenths_c,
            {{ null_if_failed_ghcn_qc('prcp') }}                AS prcp_tenths_mm,
            {{ null_if_failed_ghcn_qc('snow') }}                AS snow_mm,
            ingested_at,
            ingested_by
        FROM latest_versions
    )

-- 3. US units; measure names carry their unit
SELECT
    observation_date,
    station_id,
    -- Daily mean is (max + min) / 2, NOAA's standard definition
    ROUND((tmax_tenths_c + tmin_tenths_c) / 20 * 9 / 5 + 32, 1) AS avg_temperature_f,
    ROUND(tmax_tenths_c / 10 * 9 / 5 + 32, 1)                   AS max_temperature_f,
    ROUND(tmin_tenths_c / 10 * 9 / 5 + 32, 1)                   AS min_temperature_f,
    -- Liquid equivalent; includes melted snow
    ROUND(prcp_tenths_mm / 254, 2)                              AS precipitation_in,
    -- Depth of new snow, before melting
    ROUND(snow_mm / 25.4, 1)                                    AS snowfall_in,
    ingested_at,
    ingested_by
FROM quality_checked
