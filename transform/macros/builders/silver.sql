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


{% macro build_silver_source(partner_key, source_key) -%}
  {#
    Builds a single-source silver model: type-cast SELECT from bronze with
    incremental merge. No cross-source joins — those belong in gold.
  #}

  {%- set source_fields = get_source_dimension_definitions(partner_key, source_key) -%}
  {%- set data_fields = [] -%}
  {%- set audit_fields = [] -%}
  {%- set ns = namespace(ingestion_raw=none) -%}

  {%- for field in source_fields -%}
    {%- if field.alias == 'ingestion_timestamp' -%}
      {%- set ns.ingestion_raw = field.raw -%}
      {%- do audit_fields.append(field) -%}
    {%- elif field.alias == 'ingestion_source' -%}
      {%- do audit_fields.append(field) -%}
    {%- else -%}
      {%- do data_fields.append(field) -%}
    {%- endif -%}
  {%- endfor -%}

  {{-
    config(
      materialized='incremental',
      unique_key=get_grain_key_aliases(partner_key, source_key),
      on_schema_change='sync_all_columns'
    )
  -}}

SELECT
{%- for field in data_fields %}
    {{ cast_field(field.raw, field.type) }} AS {{ field.alias }},
{%- endfor %}
{%- for field in audit_fields %}
    {{ cast_field(field.raw, field.type) }} AS {{ field.alias }}{{ "," if not loop.last else "" }}
{%- endfor %}
FROM {{ ref(partner_key ~ '_bronze_' ~ source_key) }}
{%- if is_incremental() and ns.ingestion_raw is not none %}
WHERE {{ ns.ingestion_raw }} >= (
    SELECT COALESCE(MAX(ingestion_timestamp), TIMESTAMP('1970-01-01'))
    FROM {{ this }}
)
{%- endif %}
{%- endmacro %}

