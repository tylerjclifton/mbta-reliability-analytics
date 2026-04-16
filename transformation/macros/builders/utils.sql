{#
  Utility Macros
  
  General helper functions for working with configs and operational tasks.
#}

{# ============================================================================
   Configuration Helper Macros
   ============================================================================ #}

{% macro get_partner_config(partner_key) %}
    {# Returns the full config object for a partner #}
    {# Dynamically calls get_{partner_key}_config() macro #}
    {% set macro_name = 'get_' ~ partner_key ~ '_config' %}
    {% set config_macro = context[macro_name] %}
    {% do return(config_macro()) %}
{% endmacro %}


{% macro get_partner_sources(partner_key) %}
    {# Returns the sources object for a partner #}
    {% set partner_config = get_partner_config(partner_key) %}
    {% do return(partner_config.sources) %}
{% endmacro %}


{% macro get_source_definition(partner_key, source_key) %}
    {# Returns the definition for a specific source #}
    {% set partner_sources = get_partner_sources(partner_key) %}
    {% do return(partner_sources[source_key]) %}
{% endmacro %}


{% macro get_source_grain_keys(partner_key, source_key) %}
    {# Get the grain keys for a specific source #}
    {% set source_definition = get_source_definition(partner_key, source_key) %}
    {% do return(source_definition.grain_keys) %}
{% endmacro %}


{% macro get_source_fields(partner_key, source_key) %}
    {# Returns the fields object for a source #}
    {% set source_definition = get_source_definition(partner_key, source_key) %}
    {% do return(source_definition.fields) %}
{% endmacro %}


{% macro get_source_dimension_definitions(partner_key, source_key) %}
    {# Returns the dimension definitions array for a source #}
    {% set source_fields = get_source_fields(partner_key, source_key) %}
    {% do return(source_fields.dimensions) %}
{% endmacro %}


{% macro get_source_metric_definitions(partner_key, source_key) %}
    {# Returns the metric definitions array for a source #}
    {% set source_fields = get_source_fields(partner_key, source_key) %}
    {% do return(source_fields.metrics) %}
{% endmacro %}


{% macro get_raw_fields(partner_key, source_key) %}
    {# Extracts just the raw field names from dimension definitions #}
    {% set dimension_definitions = get_source_dimension_definitions(partner_key, source_key) %}
  
    {# Extract just the raw field names #}
    {% set raw_fields = [] %}
    {% for field in dimension_definitions %}
        {% do raw_fields.append(field.raw) %}
    {% endfor %}
  
    {% do return(raw_fields) %}
{% endmacro %}


{% macro get_partner_joins(partner_key) %}
    {# Returns the joins configuration for a partner #}
    {% set partner_config = get_partner_config(partner_key) %}
    {% set partner_joins = partner_config.get('joins', []) %}
    {% do return(partner_joins) %}
{% endmacro %}


{% macro get_base_source(partner_key) %}
    {# Get the base source for a partner (used in silver layer) #}
    {% set partner_config = get_partner_config(partner_key) %}
    {% set joins = partner_config.get('joins', []) %}
    
    {# If there are joins, use the base_source from the first join #}
    {% if joins and joins | length > 0 %}
        {% do return(joins[0].base_source) %}
    {% else %}
        {# Otherwise, return the first source in the sources dict #}
        {% set partner_sources = get_partner_sources(partner_key) %}
        {% set sources_keys = partner_sources.keys() | list %}
        {% do return(sources_keys[0]) %}
    {% endif %}
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
