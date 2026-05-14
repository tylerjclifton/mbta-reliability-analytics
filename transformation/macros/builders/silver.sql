{% macro build_silver_merge(partner_key) -%}

{%- set base_source_key = get_base_source(partner_key) -%}
{%- set base_fields = get_source_dimension_definitions(partner_key, base_source_key) -%}
{%- set grain_keys_raw = get_source_grain_keys(partner_key, base_source_key) -%}
{%- set joins = get_partner_joins(partner_key) -%}

{# Map raw field names to their aliases for grain_keys #}
{%- set grain_keys_aliases = [] -%}
{%- for raw_field in grain_keys_raw -%}
    {%- for field in base_fields -%}
        {%- if field.raw == raw_field -%}
            {%- do grain_keys_aliases.append(field.alias) -%}
        {%- endif -%}
    {%- endfor -%}
{%- endfor -%}

{{- config(
    materialized='incremental',
    unique_key=grain_keys_aliases,
    on_schema_change='sync_all_columns'
) -}}

WITH base AS (
    SELECT
{%- for field in base_fields %}
        {%- if field.type | lower == 'date' %}
        CAST(REGEXP_EXTRACT(CAST({{ field.raw }} AS STRING), r"^\d{4}-\d{2}-\d{2}") AS DATE) AS {{ field.alias }}{{ "," if not loop.last else "" }}
        {%- else %}
        CAST({{ field.raw }} AS {{ field.type | upper }}) AS {{ field.alias }}{{ "," if not loop.last else "" }}
        {%- endif %}
{%- endfor %}
    FROM {{ ref(partner_key ~ '_bronze_' ~ base_source_key) }}
)
{%- for join in joins %}
{%- set join_fields = get_source_dimension_definitions(partner_key, join.join_source) %}
,
{{ join.join_source }}_base AS (
    SELECT
{%- for field in join_fields %}
        {%- if field.type | lower == 'date' %}
        CAST(REGEXP_EXTRACT(CAST({{ field.raw }} AS STRING), r"^\d{4}-\d{2}-\d{2}") AS DATE) AS {{ field.alias }}{{ "," if not loop.last else "" }}
        {%- else %}
        CAST({{ field.raw }} AS {{ field.type | upper }}) AS {{ field.alias }}{{ "," if not loop.last else "" }}
        {%- endif %}
{%- endfor %}
    FROM {{ ref(partner_key ~ '_bronze_' ~ join.join_source) }}
)
{%- endfor %}

SELECT
    base.*
{%- for join in joins %}
{%- set join_fields = get_source_dimension_definitions(partner_key, join.join_source) %}
{%- set join_alias = join.join_source[0] %}

{# Build list of field aliases to exclude #}
{%- set exclude_aliases = [] %}
{# Add join key fields #}
{%- for on_clause in join.on %}
    {%- do exclude_aliases.append(on_clause.right) %}
{%- endfor %}
{# Add fields that already exist in base #}
{%- for base_field in base_fields %}
    {%- do exclude_aliases.append(base_field.alias) %}
{%- endfor %}

{# Select non-excluded fields from join table #}
{%- for field in join_fields %}
    {%- if field.alias not in exclude_aliases %}
    ,
    {{ join_alias }}.{{ field.alias }}
    {%- endif %}
{%- endfor %}
{%- endfor %}
FROM base
{%- for join in joins %}
{%- set join_alias = join.join_source[0] %}
{{ join.join_type | upper }} JOIN {{ join.join_source }}_base AS {{ join_alias }}
    ON {% for on_clause in join.on %}base.{{ on_clause.left }} = {{ join_alias }}.{{ on_clause.right }}{{ ' AND ' if not loop.last else '' }}{% endfor %}
{%- endfor %}

{%- endmacro %}
