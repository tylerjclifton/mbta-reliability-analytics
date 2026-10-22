{% macro generate_schema_name(custom_schema_name, node) -%}
  {#
    Use model-level schema names exactly as provided (bronze/silver/gold map
    straight to BigQuery datasets). If a model does not set schema, fall back
    to target.schema.
  #}
  {%- if custom_schema_name is none -%}
    {{ target.schema }}
  {%- else -%}
    {{ custom_schema_name | trim }}
  {%- endif -%}
{%- endmacro %}
