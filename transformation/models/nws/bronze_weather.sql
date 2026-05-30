{{
	config(
		schema='nws',
		alias='bronze_weather',
		materialized='incremental',
		unique_key=['observation_id'],
		on_schema_change='sync_all_columns'
	)
}}
{{ build_bronze_merge('nws', 'weather') }}