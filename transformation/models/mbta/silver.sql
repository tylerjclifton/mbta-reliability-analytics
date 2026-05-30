{{
	config(
		schema='mbta',
		alias='silver',
		materialized='incremental',
		unique_key=['alert_id'],
		on_schema_change='sync_all_columns'
	)
}}
{{ build_silver_merge('mbta') }}