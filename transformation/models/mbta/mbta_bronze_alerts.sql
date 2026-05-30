{{
    config(
        schema='mbta',
        alias='bronze_alerts'
    )
}}

{{ build_bronze_merge('mbta', 'alerts') }}