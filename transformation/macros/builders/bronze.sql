{# 
  Bronze Layer Model Builder (Native dbt MERGE Pattern)
  
  Generic builder that works across all data sources.
  Uses dbt's native incremental materialization with MERGE strategy:
    - dbt automatically generates MERGE statement based on unique_key
    - Updates existing records and inserts new ones atomically
    - Simpler, more maintainable, and idiomatic dbt approach
  
  Reads field config from macros/configs/{source}.sql
#}

{% macro build_bronze_merge(partner_key, source_key) -%}

{%- set source_config = get_source_config(partner_key, source_key) -%}
{%- set raw_fields = get_raw_fields(partner_key, source_key) -%}
{%- set grain_keys = source_config.grain_keys -%}
{%- set staging_table = source_config.staging_table -%}
{%- set project_id = env_var('DBT_PROJECT_ID', 'mbta-reliability-analytics') -%}

{{-
    config(
        materialized='incremental',
        unique_key=grain_keys,
        on_schema_change='sync_all_columns'
    )
-}}

{# Select all data from staging - dbt handles MERGE automatically #}
SELECT
{%- for field in raw_fields %}
    {{ field }}{{ "," if not loop.last else "" }}
{%- endfor %}
FROM `{{ project_id }}.staging.{{ staging_table }}`

{% endmacro %}
