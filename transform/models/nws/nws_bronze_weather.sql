{{-
    config(
        schema='nws',
        alias='bronze_weather'
    )
 -}}

{{- build_bronze_merge('nws', 'weather') -}}