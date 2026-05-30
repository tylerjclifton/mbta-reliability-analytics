{{
	config(
		schema='mbta',
		alias='bronze_alerts',
		materialized='incremental',
		unique_key=['alert_id'],
		on_schema_change='sync_all_columns'
	)
}}
{{ build_bronze_merge('mbta', 'alerts') }}
