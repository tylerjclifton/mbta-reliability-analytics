{% macro build_bronze_merge(partner_key, source_key) -%}

{%- set source_definition = get_source_definition(partner_key, source_key) -%}
{%- set raw_fields = get_raw_fields(partner_key, source_key) -%}
{%- set grain_keys = get_source_grain_keys(partner_key, source_key) -%}
{%- set source_dataset = source_definition.staging.dataset -%}
{%- set source_table = source_definition.staging.table -%}
{%- set project_id = env_var('DBT_PROJECT_ID', 'mbta-reliability-analytics') -%}

{{-
    config(
        materialized='incremental',
        unique_key=grain_keys,
        on_schema_change='sync_all_columns'
    )
-}}

SELECT
{%- for field in raw_fields %}
    {{ field }}{{ "," if not loop.last else "" }}
{%- endfor %}
FROM `{{ target.project }}.{{ source_dataset }}.{{ source_table }}`

{% endmacro %}
