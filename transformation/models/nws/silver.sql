{{
	config(
		schema='nws',
		alias='silver',
		materialized='incremental',
		unique_key=['observation_id'],
		on_schema_change='sync_all_columns'
	)
}}
{{ build_silver_merge('nws') }}