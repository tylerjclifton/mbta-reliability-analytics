{{-
    config(
        schema='mbta',
        alias='silver_routes'
    )
 -}}

{{- build_silver_source('mbta', 'routes') -}}
