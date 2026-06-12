{#
  Gold Layer Model Builder (Cross-Source Analytics)

  Generic builder for the gold/analytics layer that combines multiple sources.
  Designed for flexible cross-source joins (e.g., MBTA + NWS).

  Pattern:
    1. Base CTE: Primary analytical source
    2. Join CTEs: Additional sources with aggregations/transformations
    3. Final SELECT: Combined analytical dataset

  Uses dbts native incremental MERGE strategy with unique_key.
#}

{% macro build_gold_cross_source(config) -%}
  {%- set grain_keys = config.get('grain_keys') -%}
  {%- if grain_keys is none -%}
    {% do exceptions.raise_compiler_error("build_gold_cross_source requires config['grain_keys']") %}
  {%- endif -%}

  {{-
    config(
      materialized='incremental',
      unique_key=grain_keys,
      on_schema_change='sync_all_columns'
    )
  -}}

  {%- set base_table = config['base_table'] -%}
  {%- set joins = config['joins'] -%}

  WITH base AS (
    SELECT *
    FROM {{ ref(base_table) }}
  )
  {%- for join in joins %}
    ,
    {{ join['name'] }}_agg AS (
      SELECT
        {%- for field in join['group_by'] %}
          {{ field }},
        {%- endfor %}
        {%- for agg in join['aggregations'] %}
          {{ agg['expression'] }} AS {{ agg['alias'] }}{{ "," if not loop.last else "" }}
        {%- endfor %}
      FROM {{ ref(join['table']) }}
      GROUP BY {{ join['group_by'] | join(', ') }}
    )
  {%- endfor %}

  SELECT
    base.*
    {%- for join in joins %}
      {%- for agg in join['aggregations'] %}
        ,
        {{ join['name'] }}_agg.{{ agg['alias'] }}
      {%- endfor %}
    {%- endfor %}
  FROM base
  {%- for join in joins %}
    {# Join condition is provided by the config object for each source. #}
    {{ join['join_type'] | upper }} JOIN {{ join['name'] }}_agg
      ON {{ join['on'] }}
  {%- endfor %}

{% endmacro %}
