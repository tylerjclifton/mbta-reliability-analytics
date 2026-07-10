{#
  Maintenance Macros
  Operational dbt utilities (cleanup, housekeeping, etc.).
#}

{% macro drop_temp_tables() %}
  {#
    Drop Temporary Tables Macro
    Automatically cleans up any __dbt_tmp tables left over from incremental runs.
    Executed as a post-hook after each dbt run.
  #}
  {% if execute %}
    {% set project_id = env_var('DBT_PROJECT_ID', 'mbta-reliability-analytics') %}
    {% set get_temp_tables_query %}
      SELECT table_schema, table_name
      FROM `{{ project_id }}.region-us-east1.INFORMATION_SCHEMA.TABLES`
      WHERE table_name LIKE '%__dbt_tmp'
        AND table_type = 'BASE TABLE'
    {% endset %}
    {% set temp_tables = run_query(get_temp_tables_query) %}
    {% if temp_tables %}
      {% for row in temp_tables %}
        {% set drop_sql %}
          DROP TABLE IF EXISTS `{{ project_id }}.{{ row[0] }}.{{ row[1] }}`
        {% endset %}
        {% do log("Dropping temporary table: " ~ row[0] ~ "." ~ row[1], info=True) %}
        {% do run_query(drop_sql) %}
      {% endfor %}
    {% endif %}
  {% endif %}
{% endmacro %}

{% macro generate_schema_name(custom_schema_name, node) -%}
  {#
    Use model-level schema names exactly as provided.
    If a model does not set schema, fall back to target.schema.
  #}
  {%- if custom_schema_name is none -%}
    {{ target.schema }}
  {%- else -%}
    {{ custom_schema_name | trim }}
  {%- endif -%}
{%- endmacro %}
