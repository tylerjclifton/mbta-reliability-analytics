{% macro build_bronze_merge(partner_key, source_key) -%}
  {# Configure incremental merge behavior for bronze tables. #}
  {{
    config(
      materialized='incremental',
      unique_key=get_source_grain_keys(partner_key, source_key),
      on_schema_change='sync_all_columns'
    )
  }}

  {# Resolve source metadata from partner config. #}
  {%- set source_definition = get_source_definition(partner_key, source_key) -%}
  {%- set source_dataset = source_definition.staging.dataset -%}
  {%- set source_table = source_definition.staging.table -%}
  {%- set raw_fields = get_raw_fields(partner_key, source_key) -%}

  {# Build the raw select list dynamically to keep field mapping centralized in configs. #}
  {%- set select_statement -%}
    SELECT
      {%- for field in raw_fields %}
        {{ field }}{{ "," if not loop.last else "" }}
      {%- endfor %}
    FROM `{{ target.project }}.{{ source_dataset }}.{{ source_table }}`
  {%- endset %}

  {{ select_statement }}
{% endmacro %}
