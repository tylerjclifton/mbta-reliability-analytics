{# 
  Bronze Layer Model Builder (Native dbt MERGE Pattern)
  
  Generic builder that works across all data sources.
  Uses dbt's native incremental materialization with MERGE strategy:
    - dbt automatically generates MERGE statement based on unique_key
    - Updates existing records and inserts new ones atomically
    - Simpler, more maintainable, and idiomatic dbt approach
  
  Reads field config from macros/configs/{source}.sql
#}

{% macro build_bronze_desert(partner, source_name) %}

{% set source_config = get_source_config(partner, source_name) %}
{% set raw_fields = get_raw_fields(partner, source_name) %}
{% set unique_key = source_config.unique_key %}
{% set staging_table = source_config.staging_table %}
{% set project_id = env_var('DBT_PROJECT_ID', 'mbta-reliability-analytics') %}

{{
    config(
        materialized='incremental',
        unique_key=unique_key,
        on_schema_change='sync_all_columns'
    )
}}

{# Select all data from staging - dbt handles MERGE automatically #}
select
    {% for field in raw_fields -%}
    {{ field }}{{ "," if not loop.last else "" }}
    {% endfor %}
from `{{ project_id }}.staging.{{ staging_table }}`

{% endmacro %}
