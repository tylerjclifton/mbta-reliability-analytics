{# 
  Configuration Helper Macros
  
  Shared helper functions that work across all partner configs.
  Each partner file (mbta.sql, nws.sql) defines: get_partner_field_config(partner, source_name)
  
  These helpers extract specific attributes from the config dict returned by partner files.
#}

{% macro get_raw_fields(partner, source_name) %}
  {# Get field config for source #}
  {% set source_config = get_partner_field_config(partner, source_name) %}
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
  {% set source_config = get_partner_field_config(partner, source_name) %}
  {% do return(source_config.unique_key) %}
{% endmacro %}


{% macro get_delete_key_field(partner, source_name) %}
  {# Get the primary delete key field (first field with _id, or first unique_key field) #}
  {% set source_config = get_partner_field_config(partner, source_name) %}
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
  {% set source_config = get_partner_field_config(partner, source_name) %}
  {% do return(source_config.staging_table) %}
{% endmacro %}
