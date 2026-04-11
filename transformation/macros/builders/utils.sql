{#
  Utility Macros
  
  General helper functions for working with configs and operational tasks.
#}

{# ============================================================================
   Configuration Helper Macros
   ============================================================================ #}

{% macro get_partner_config(partner) %}
    {# Returns the full config object for a partner #}
    {% if partner == 'mbta' %}
    {% do return(get_mbta_config()) %}
  {% elif partner == 'nws' %}
    {% do return(get_nws_config()) %}
  {% else %}
        {% do return(none) %}
    {% endif %}
{% endmacro %}

{% macro get_source_config(partner, source_name) %}
    {# Returns the config for a specific source #}
    {% set full_config = get_partner_config(partner) %}
    {% do return(full_config.sources[source_name]) %}
{% endmacro %}

{% macro get_partner_joins(partner, source_name) %}
    {# Returns the joins configuration for a specific source #}
    {% set full_config = get_partner_config(partner) %}
    {% set all_joins = full_config.get('joins', []) %}
    {% set source_joins = [] %}
  
    {# Filter joins for this specific source #}
    {% for join in all_joins %}
        {% if join.base_source == source_name %}
            {% do source_joins.append(join) %}
        {% endif %}
    {% endfor %}
  
    {% do return(source_joins) %}
{% endmacro %}


{% macro get_raw_fields(partner, source_name) %}
    {# Get field config for source #}
    {% set source_config = get_source_config(partner, source_name) %}
    {% set fields = source_config.fields %}
  
    {# Extract just the raw field names #}
    {% set raw_fields = [] %}
    {% for field in fields %}
        {% do raw_fields.append(field.raw) %}
    {% endfor %}
  
    {% do return(raw_fields) %}
{% endmacro %}


{% macro get_unique_key(partner, source_name) %}
    {# Get the unique key configuration for incremental models #}
    {% set source_config = get_source_config(partner, source_name) %}
    {% do return(source_config.unique_key) %}
{% endmacro %}


{% macro get_delete_key_field(partner, source_name) %}
    {# Get the primary delete key field (first field with _id, or first unique_key field) #}
    {% set source_config = get_source_config(partner, source_name) %}
    {% set fields = source_config.fields %}
  
    {# Try to find a field ending in _id #}
    {% for field in fields %}
        {% if field.raw.endswith('_id') %}
            {% do return(field.raw) %}
        {% endif %}
    {% endfor %}
  
    {# Otherwise, return the first unique_key field #}
    {% do return(source_config.unique_key[0]) %}
{% endmacro %}


{% macro get_staging_table(partner, source_name) %}
    {# Get the staging table name for a source #}
    {% set source_config = get_source_config(partner, source_name) %}
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
