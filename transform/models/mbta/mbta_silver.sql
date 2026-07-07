{{-
    config(
        schema='mbta',
        alias='silver',
        unique_key=['alert_id', 'route_id']
    )
 -}}

{{- build_silver_merge('mbta') -}}