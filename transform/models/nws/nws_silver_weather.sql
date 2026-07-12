{{-
    config(
        schema='nws',
        alias='silver_weather'
    )
 -}}

{{- build_silver_source('nws', 'weather') -}}
