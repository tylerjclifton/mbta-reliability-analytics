{# 
  Silver Layer Model Builder (CTE + JOIN Pattern)
  
  Generic builder that works across all data sources.
  Creates modular CTEs for each source with transformations, then joins them.
  
  Pattern:
    1. Base CTE: Main source with field renaming and type casting
    2. Join CTEs: Each joined source with its field transformations
    3. Final SELECT: Joins all CTEs based on config
  
  Uses dbt's native incremental MERGE strategy with unique_key.
  Reads field config and join config from macros/configs/{partner}.sql
#}

{% macro build_silver_with_joins(partner, source_name) %}

    {% set source_config = get_source_config(partner, source_name) %}
    {% set base_fields = source_config.fields %}
    {% set unique_key_raw = source_config.unique_key %}
    {% set joins = get_partner_joins(partner, source_name) %}

    {# Map raw field names to their aliases for unique_key #}
    {% set unique_key_aliases = [] %}
    {% for raw_field in unique_key_raw %}
        {% for field in base_fields %}
            {% if field.raw == raw_field %}
                {% do unique_key_aliases.append(field.alias) %}
            {% endif %}
        {% endfor %}
    {% endfor %}

{{
    config(
        materialized='incremental',
        unique_key=unique_key_aliases,
        on_schema_change='sync_all_columns'
    )
}}

WITH base AS (
    SELECT
        {% for field in base_fields %}
        {% if field.type | lower == 'date' %}
        CAST(REGEXP_EXTRACT(CAST({{ field.raw }} AS STRING), r"^\d{4}-\d{2}-\d{2}") AS DATE) AS {{ field.alias }}{{ "," if not loop.last else "" }}
        {% else %}
        CAST({{ field.raw }} AS {{ field.type | upper }}) AS {{ field.alias }}{{ "," if not loop.last else "" }}
        {% endif %}
        {% endfor %}
    FROM {{ ref(partner ~ '_bronze_' ~ source_name) }}
)

{# Generate CTE for each joined source #}
{% for join in joins %}
{% set join_config = get_source_config(partner, join.join_source) %}
{% set join_fields = join_config.fields %}
,

{{ join.join_source }}_base AS (
    SELECT
        {% for field in join_fields %}
        {% if field.type | lower == 'date' %}
        CAST(REGEXP_EXTRACT(CAST({{ field.raw }} AS STRING), r"^\d{4}-\d{2}-\d{2}") AS DATE) AS {{ field.alias }}{{ "," if not loop.last else "" }}
        {% else %}
        CAST({{ field.raw }} AS {{ field.type | upper }}) AS {{ field.alias }}{{ "," if not loop.last else "" }}
        {% endif %}
        {% endfor %}
    FROM {{ ref(partner ~ '_bronze_' ~ join.join_source) }}
)
{% endfor %}

{# Final SELECT with joins #}
SELECT
    base.*
    {# Add fields from joined sources #}
    {% for join in joins %}
    {% set join_config = get_source_config(partner, join.join_source) %}
    {% set join_fields = join_config.fields %}
    {# Get the alias from the first character of the join source #}
    {% set join_alias = join.join_source[0] %}
    {% for field in join_fields %}
        {# Skip join key fields to avoid duplicates #}
        {% set is_join_key = false %}
        {% for on_clause in join.on %}
        {% if field.raw == on_clause.right %}
            {% set is_join_key = true %}
        {% endif %}
        {% endfor %}
        {% if not is_join_key %}
    ,
    {{ join_alias }}.{{ field.alias }}
        {% endif %}
    {% endfor %}
    {% endfor %}
FROM base
{% for join in joins %}
{% set join_alias = join.join_source[0] %}
{{ join.join_type | upper }} JOIN {{ join.join_source }}_base AS {{ join_alias }}
    ON {% for on_clause in join.on %}base.{{ on_clause.left }} = {{ join_alias }}.{{ on_clause.right }}{{ ' AND ' if not loop.last else '' }}{% endfor %}
{% endfor %}

{% endmacro %}
