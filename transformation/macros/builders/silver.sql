{% macro get_grain_key_aliases(partner_key, source_key) -%}
  {%- set fields = get_source_dimension_definitions(partner_key, source_key) -%}
  {%- set grain_keys_raw = get_source_grain_keys(partner_key, source_key) -%}
  {%- set grain_keys_aliases = [] -%}

  {%- for raw_field in grain_keys_raw -%}
    {%- for field in fields -%}
      {%- if field.raw == raw_field -%}
        {%- do grain_keys_aliases.append(field.alias) -%}
      {%- endif -%}
    {%- endfor -%}
  {%- endfor -%}

  {% do return(grain_keys_aliases) %}
{%- endmacro %}

{% macro build_silver_merge(partner_key) -%}
  {{-
    config(
      materialized='incremental',
      unique_key=get_grain_key_aliases(partner_key, get_base_source(partner_key)),
      on_schema_change='sync_all_columns'
    )
  -}}

  {%- set base_source_key = get_base_source(partner_key) -%}
  {%- set base_fields = get_source_dimension_definitions(partner_key, base_source_key) -%}
  {%- set joins = get_partner_joins(partner_key) -%}

  WITH base_{{ base_source_key }} AS (
    SELECT
      {%- for field in base_fields %}
        {%- if field.type | lower == 'date' %}
          {# Some inputs include datetime strings; extract the date portion safely. #}
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
    base_{{ join.join_source }} AS (
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
  {%- if joins | length > 0 %}
    {%- for field in base_fields %}
      base_{{ base_source_key }}.{{ field.alias }}{{ "," if not loop.last or joins | length > 0 else "" }}
    {%- endfor %}
  {%- else %}
    *
  {%- endif %}
  {%- for join in joins %}
    {%- set join_fields = get_source_dimension_definitions(partner_key, join.join_source) %}
    {%- set join_alias = 'base_' ~ join.join_source %}

    {# Keep join keys and duplicate aliases from being selected twice. #}
    {%- set exclude_aliases = [] %}
    {%- for on_clause in join.on %}
      {%- do exclude_aliases.append(on_clause.right) %}
    {%- endfor %}
    {%- for base_field in base_fields %}
      {%- do exclude_aliases.append(base_field.alias) %}
    {%- endfor %}

    {%- for field in join_fields %}
      {%- if field.alias not in exclude_aliases %}
        ,
        {{ join_alias }}.{{ field.alias }}
      {%- endif %}
    {%- endfor %}
  {%- endfor %}
  FROM base_{{ base_source_key }}
  {%- for join in joins %}
    {%- set join_alias = 'base_' ~ join.join_source %}
    {{ join.join_type | upper }} JOIN {{ join_alias }} AS {{ join_alias }}
      ON {% for on_clause in join.on %}base_{{ base_source_key }}.{{ on_clause.left }} = {{ join_alias }}.{{ on_clause.right }}{{ ' AND ' if not loop.last else '' }}{% endfor %}
  {%- endfor %}

{%- endmacro %}
