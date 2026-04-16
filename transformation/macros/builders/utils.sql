{#
  Utility Macros
  
  General helper functions for working with configs and operational tasks.
#}

{# ============================================================================
   Configuration Helper Macros
   ============================================================================ #}

{% macro get_partner_config(partner_key) %}
    {# Returns the full config object for a partner #}
    {% if partner_key == 'mbta' %}
    {% do return(get_mbta_config()) %}
  {% elif partner_key == 'nws' %}
    {% do return(get_nws_config()) %}
  {% else %}
        {% do return(none) %}
    {% endif %}
{% endmacro %}

{% macro get_source_config(partner_key, source_key) %}
    {# Returns the config for a specific source #}
    {% set full_config = get_partner_config(partner_key) %}
    {% do return(full_config.sources[source_key]) %}
{% endmacro %}

{% macro get_partner_joins(partner_key) %}
    {# Returns the joins configuration for a partner #}
    {% set full_config = get_partner_config(partner_key) %}
    {% set all_joins = full_config.get('joins', []) %}
    {% do return(all_joins) %}
{% endmacro %}


{% macro get_base_source(partner_key) %}
    {# Get the base source for a partner (used in silver layer) #}
    {% set full_config = get_partner_config(partner_key) %}
    {% set joins = full_config.get('joins', []) %}
    
    {# If there are joins, use the base_source from the first join #}
    {% if joins and joins | length > 0 %}
        {% do return(joins[0].base_source) %}
    {% else %}
        {# Otherwise, return the first source in the sources dict #}
        {% set sources_keys = full_config.sources.keys() | list %}
        {% do return(sources_keys[0]) %}
    {% endif %}
{% endmacro %}


{% macro get_raw_fields(partner_key, source_key) %}
    {# Get field config for source #}
    {% set source_config = get_source_config(partner_key, source_key) %}
    {% set fields = source_config.fields.dimensions %}
  
    {# Extract just the raw field names #}
    {% set raw_fields = [] %}
    {% for field in fields %}
        {% do raw_fields.append(field.raw) %}
    {% endfor %}
  
    {% do return(raw_fields) %}
{% endmacro %}


{% macro get_grain_keys(partner_key, source_key) %}
    {# Get the grain key configuration for incremental models #}
    {% set source_config = get_source_config(partner_key, source_key) %}
    {% do return(source_config.grain_keys) %}
{% endmacro %}


{% macro get_delete_key_field(partner_key, source_key) %}
    {# Get the primary delete key field (first field with _id, or first grain_keys field) #}
    {% set source_config = get_source_config(partner_key, source_key) %}
    {% set fields = source_config.fields.dimensions %}
  
    {# Try to find a field ending in _id #}
    {% for field in fields %}
        {% if field.raw.endswith('_id') %}
            {% do return(field.raw) %}
        {% endif %}
    {% endfor %}
  
    {# Otherwise, return the first grain_keys field #}
    {% do return(source_config.grain_keys[0]) %}
{% endmacro %}


{% macro get_staging_table(partner_key, source_key) %}
    {# Get the staging table name for a source #}
    {% set source_config = get_source_config(partner_key, source_key) %}
    {% do return(source_config.staging_table) %}
{% endmacro %}


{# ============================================================================
   Operational Utilities
   ============================================================================ #}

{% macro drop_temp_tables() %}
  {#
    Drop Temporary Tables Macro
    
    Automatically cleans up any __dbt_tmp tables left over from incremental runs.
    Executed as a post-hook after each dbt run.
  #}
    {% if execute %}
    {% set project_id = env_var('DBT_PROJECT_ID', 'mbta-reliability-analytics') %}
    {% set dataset = target.dataset %}
    
    {# Query to find all __dbt_tmp tables in the dataset #}
    {% set get_temp_tables_query %}
      SELECT table_name
      FROM `{{ project_id }}.{{ dataset }}.INFORMATION_SCHEMA.TABLES`
      WHERE table_name LIKE '%__dbt_tmp'
    {% endset %}
    
    {% set temp_tables = run_query(get_temp_tables_query) %}
    
    {% if temp_tables %}
      {% for row in temp_tables %}
        {% set table_name = row[0] %}
        {% set drop_sql %}
          DROP TABLE IF EXISTS `{{ project_id }}.{{ dataset }}.{{ table_name }}`
        {% endset %}
        
        {% do log("Dropping temporary table: " ~ table_name, info=True) %}
        {% do run_query(drop_sql) %}
      {% endfor %}
    {% endif %}
  {% endif %}
{% endmacro %}
