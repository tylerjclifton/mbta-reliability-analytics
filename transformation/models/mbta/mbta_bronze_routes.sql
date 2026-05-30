{{
    config(
        schema='mbta',
        alias='bronze_routes'
    )
}}

{{ build_bronze_merge('mbta', 'routes') }}