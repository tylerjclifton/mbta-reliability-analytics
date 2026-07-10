{{-
    config(
        schema='mbta',
        alias='silver_ridership'
    )
 -}}

{{- build_silver_source('mbta', 'ridership') -}}
