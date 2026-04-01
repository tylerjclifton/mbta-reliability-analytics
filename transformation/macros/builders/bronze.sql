{# 
  Bronze Layer Model Builder (Explicit DELETE + INSERT Pattern)
  
  Generic builder that works across all data sources.
  Implements explicit DELETE + INSERT:
    1. DELETE: Pre-hook executes DELETE FROM bronze WHERE keys match staging
    2. INSERT: Main query executes INSERT INTO bronze SELECT FROM staging
  
  Reads field config from macros/configs/{source}.sql
  Mirrors Dataform's buildDesertBronze() function.
#}

{% macro build_bronze_desert(partner, source_name) %}

{% set source_config = get_partner_config(partner, source_name) %}
{% set raw_fields = get_raw_fields(partner, source_name) %}
{% set unique_key = source_config.unique_key %}
{% set staging_table = source_config.staging_table %}
{% set project_id = env_var('DBT_PROJECT_ID', 'mbta-reliability-analytics') %}

{# Build WHERE clause for DELETE based on unique_key #}
{% set delete_where_conditions = [] %}
{% for key_field in unique_key %}
  {% do delete_where_conditions.append(key_field ~ " IN (SELECT DISTINCT " ~ key_field ~ " FROM `" ~ project_id ~ ".staging." ~ staging_table ~ "`)") %}
{% endfor %}

{{
    config(
        materialized='incremental',
        on_schema_change='sync_all_columns'
    )
}}

{# Execute DELETE before INSERT when incremental #}
{%if is_incremental() %}
  {% set delete_sql %}
    DELETE FROM `{{ project_id }}.{{ target.dataset }}.{{ partner }}_bronze_{{ source_name }}`
    WHERE {{ delete_where_conditions[0] }}
  {% endset %}
  
  {% do run_query(delete_sql) %}
{% endif %}

{# INSERT: Select all data from staging (will append after DELETE) #}
select
    {% for field in raw_fields -%}
    {{ field }}{{ "," if not loop.last else "" }}
    {% endfor %}
from `{{ project_id }}.staging.{{ staging_table }}`

{% endmacro %}
