{{-
    config(
        schema='mbta',
        alias='bronze_ridership'
    )
 -}}

{{- build_bronze_merge('mbta', 'ridership') -}}
