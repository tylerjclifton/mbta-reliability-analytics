{{
	config(
		schema='mbta',
		alias='bronze_routes',
		materialized='incremental',
		unique_key=['route_id'],
		on_schema_change='sync_all_columns'
	)
}}
{{ build_bronze_merge('mbta', 'routes') }}
