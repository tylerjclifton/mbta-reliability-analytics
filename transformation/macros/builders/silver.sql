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

  {%- do return(grain_keys_aliases) -%}
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
  {%- set base_source_definition = get_source_definition(partner_key, base_source_key) -%}
  {%- set base_fields = get_source_dimension_definitions(partner_key, base_source_key) -%}
  {%- set joins = get_partner_joins(partner_key) -%}
  {%- set join_select_columns = [] -%}
  {%- set base_data_fields = [] -%}
  {%- set base_audit_fields = [] -%}
  {%- set ns = namespace(base_ingestion_raw=none) -%}

  {%- for field in base_source_definition.fields.dimensions -%}
    {%- if field.alias == 'ingestion_timestamp' -%}
      {%- set ns.base_ingestion_raw = field.raw -%}
      {%- do base_audit_fields.append(field) -%}
    {%- elif field.alias == 'ingestion_source' -%}
      {%- do base_audit_fields.append(field) -%}
    {%- else -%}
      {%- do base_data_fields.append(field) -%}
    {%- endif -%}
  {%- endfor -%}

  {%- for join in joins -%}
    {%- set join_fields = get_source_dimension_definitions(partner_key, join.join_source) -%}
    {%- set join_alias = 'base_' ~ join.join_source -%}

    {# Keep join keys and duplicate aliases from being selected twice. #}
    {%- set exclude_aliases = [] -%}
    {%- for on_clause in join.on -%}
      {%- do exclude_aliases.append(on_clause.right) -%}
    {%- endfor -%}
    {%- for base_field in base_fields -%}
      {%- do exclude_aliases.append(base_field.alias) -%}
    {%- endfor -%}

    {%- for field in join_fields -%}
      {%- if field.alias not in exclude_aliases -%}
        {%- do join_select_columns.append(join_alias ~ '.' ~ field.alias) -%}
      {%- endif -%}
    {%- endfor -%}
  {%- endfor -%}

  {%- set sql -%}
WITH

    base_{{ base_source_key }} AS (
        SELECT
    {%- for field in base_fields %}
            {{ ('CAST(REGEXP_EXTRACT(CAST(' ~ field.raw ~ ' AS STRING), r"^\\d{4}-\\d{2}-\\d{2}") AS DATE) AS ' ~ field.alias) if field.type | lower == 'date' else ('CAST(' ~ field.raw ~ ' AS ' ~ (field.type | upper) ~ ') AS ' ~ field.alias) }}{{ "," if not loop.last else "" }}
    {%- endfor %}
        FROM {{ ref(partner_key ~ '_bronze_' ~ base_source_key) }}
{%- if is_incremental() and ns.base_ingestion_raw is not none %}
        WHERE {{ ns.base_ingestion_raw }} >= (
            SELECT COALESCE(MAX(ingestion_timestamp), TIMESTAMP('1970-01-01'))
            FROM {{ this }}
        )
{%- endif %}
    ){% if joins | length > 0 %},{% endif %}
  {%- for join in joins %}

    base_{{ join.join_source }} AS (
        SELECT
    {%- set join_fields = get_source_dimension_definitions(partner_key, join.join_source) -%}
  {%- for field in join_fields %}
          {{ ('CAST(REGEXP_EXTRACT(CAST(' ~ field.raw ~ ' AS STRING), r"^\\d{4}-\\d{2}-\\d{2}") AS DATE) AS ' ~ field.alias) if field.type | lower == 'date' else ('CAST(' ~ field.raw ~ ' AS ' ~ (field.type | upper) ~ ') AS ' ~ field.alias) }}{{ "," if not loop.last else "" }}
  {%- endfor %}
        FROM {{ ref(partner_key ~ '_bronze_' ~ join.join_source) }}
    ){% if not loop.last %},{% endif %}
  {%- endfor %}

SELECT
  {%- if joins | length > 0 %}
    {%- for field in base_data_fields %}
    base_{{ base_source_key }}.{{ field.alias }}{{ "," if not loop.last or join_select_columns | length > 0 or base_audit_fields | length > 0 else "" }}
    {%- endfor %}
    {%- for column in join_select_columns %}
    {{ column }}{{ "," if not loop.last or base_audit_fields | length > 0 else "" }}
    {%- endfor %}
    {%- for field in base_audit_fields %}
    base_{{ base_source_key }}.{{ field.alias }}{{ "," if not loop.last else "" }}
    {%- endfor %}
  {%- else %}
    {%- for field in base_data_fields %}
    base_{{ base_source_key }}.{{ field.alias }}{{ "," if not loop.last or base_audit_fields | length > 0 else "" }}
    {%- endfor %}
    {%- for field in base_audit_fields %}
    base_{{ base_source_key }}.{{ field.alias }}{{ "," if not loop.last else "" }}
    {%- endfor %}
  {%- endif %}
FROM base_{{ base_source_key }}
{% for join in joins %}
    {%- set join_alias = 'base_' ~ join.join_source -%}
    {%- set join_conditions = [] -%}
    {%- for on_clause in join.on -%}
      {%- do join_conditions.append('base_' ~ base_source_key ~ '.' ~ on_clause.left ~ ' = ' ~ join_alias ~ '.' ~ on_clause.right) -%}
    {%- endfor -%}
{{ join.join_type | upper }} JOIN {{ join_alias }} AS {{ join_alias }}
    ON {{ join_conditions | join(' AND ') }}
{% endfor %}
  {%- endset -%}

  {{ sql }}
{%- endmacro %}
