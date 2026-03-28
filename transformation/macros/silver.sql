{# 
  Silver Layer Model Builder (Desert Pattern)
  
  Generic builder that works across all data sources.
  Implements MERGE pattern (BigQuery equivalent of DELETE-INSERT):
    - Matches on unique_key to update existing rows
    - Inserts new rows with type casting and field renaming
  
  Reads field config from macros/configs/{source}.sql
  Mirrors Dataform's buildCteBase() function with desert pattern.
#}

{% macro build_silver_desert(partner, source_name) %}

{% set source_config = get_partner_field_config(partner, source_name) %}
{% set fields = source_config.fields %}
{% set unique_key_raw = source_config.unique_key %}

{# Map raw field names to their aliases for unique_key #}
{% set unique_key_aliases = [] %}
{% for raw_field in unique_key_raw %}
  {% for field in fields %}
    {% if field.raw == raw_field %}
      {% do unique_key_aliases.append(field.alias) %}
    {% endif %}
  {% endfor %}
{% endfor %}

{# Build WHERE clause for DELETE based on unique_key (using aliases) #}
{% set delete_where_conditions = [] %}
{% for i in range(unique_key_raw | length) %}
  {% do delete_where_conditions.append("target." ~ unique_key_aliases[i] ~ " = source." ~ unique_key_raw[i]) %}
{% endfor %}
{% set delete_where = delete_where_conditions | join(' AND ') %}

{# DELETE statement in pre-hook #}
{% set delete_sql %}
  DELETE FROM {{ this }} AS target
  WHERE EXISTS (
    SELECT 1 FROM {{ ref('bronze_' ~ source_name) }} AS source
    WHERE {{ delete_where }}
  )
{% endset %}

{{
    config(
        materialized='incremental',
        on_schema_change='sync_all_columns',
        pre_hook="{{ delete_sql if is_incremental() else '' }}"
    )
}}

{# Select all data from bronze with type casting and renaming #}
select
    {% for field in fields %}
    {% if field.type | lower == 'date' %}
    cast(regexp_extract(cast({{ field.raw }} as string), r"^\d{4}-\d{2}-\d{2}") as date) as {{ field.alias }}{{ "," if not loop.last else "" }}
    {% else %}
    cast({{ field.raw }} as {{ field.type | upper }}) as {{ field.alias }}{{ "," if not loop.last else "" }}
    {% endif %}
    {% endfor %}
from {{ ref('bronze_' ~ source_name) }}

{% endmacro %}
