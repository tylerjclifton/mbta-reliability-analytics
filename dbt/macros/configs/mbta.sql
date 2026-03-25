{# 
  MBTA Source Configuration
  
  This file contains field definitions as Jinja dictionary that the bronze and 
  silver builders (macros/builders/) use at compile time.
  
  NOTE: A human-readable YAML version exists at models/mbta/config_mbta.yml
  When updating field definitions, update BOTH files to keep them in sync.
  
  Mirrors the Dataform config.js structure.
#}

{% macro get_field_config(source_name) %}
  {% set config = {
    'alerts': {
      'staging_table': 'mbta_alerts',
      'unique_key': ['alert_id', 'route'],
      'fields': [
        {'raw': 'active_period_start', 'alias': 'alert_start_date', 'type': 'date'},
        {'raw': 'active_period_end', 'alias': 'alert_end_date', 'type': 'date'},
        {'raw': 'alert_id', 'alias': 'alert_id', 'type': 'string'},
        {'raw': 'route', 'alias': 'route_id', 'type': 'string'},
        {'raw': 'header', 'alias': 'alert_header', 'type': 'string'},
        {'raw': 'description', 'alias': 'alert_description', 'type': 'string'},
        {'raw': 'cause', 'alias': 'alert_cause', 'type': 'string'},
        {'raw': 'effect', 'alias': 'alert_effect', 'type': 'string'},
        {'raw': 'severity', 'alias': 'alert_severity', 'type': 'int64'},
        {'raw': 'duration_certainty', 'alias': 'alert_duration_certainty', 'type': 'string'},
        {'raw': 'created_at', 'alias': 'alert_created_at', 'type': 'date'},
        {'raw': 'updated_at', 'alias': 'alert_updated_at', 'type': 'date'},
        {'raw': 'ingestion_timestamp', 'alias': 'ingestion_timestamp', 'type': 'timestamp'},
        {'raw': 'ingestion_source', 'alias': 'ingestion_source', 'type': 'string'}
      ]
    },
    'routes': {
      'staging_table': 'mbta_routes',
      'unique_key': ['route_id'],
      'fields': [
        {'raw': 'route_id', 'alias': 'route_id', 'type': 'string'},
        {'raw': 'long_name', 'alias': 'route_name', 'type': 'string'},
        {'raw': 'description', 'alias': 'route_description', 'type': 'string'},
        {'raw': 'route_type', 'alias': 'route_type', 'type': 'string'},
        {'raw': 'color', 'alias': 'route_color', 'type': 'string'},
        {'raw': 'direction_destinations', 'alias': 'route_destinations', 'type': 'string'},
        {'raw': 'ingestion_timestamp', 'alias': 'ingestion_timestamp', 'type': 'timestamp'},
        {'raw': 'ingestion_source', 'alias': 'ingestion_source', 'type': 'string'}
      ]
    },
    'weather': {
      'staging_table': 'nws_weather',
      'unique_key': ['observation_timestamp', 'station_id'],
      'fields': [
        {'raw': 'observation_timestamp', 'alias': 'observation_timestamp', 'type': 'timestamp'},
        {'raw': 'station_id', 'alias': 'station_id', 'type': 'string'},
        {'raw': 'temperature_fahrenheit', 'alias': 'temperature_fahrenheit', 'type': 'float64'},
        {'raw': 'temperature_celsius', 'alias': 'temperature_celsius', 'type': 'float64'},
        {'raw': 'dewpoint_fahrenheit', 'alias': 'dewpoint_fahrenheit', 'type': 'float64'},
        {'raw': 'dewpoint_celsius', 'alias': 'dewpoint_celsius', 'type': 'float64'},
        {'raw': 'wind_speed_mph', 'alias': 'wind_speed_mph', 'type': 'float64'},
        {'raw': 'wind_direction_degrees', 'alias': 'wind_direction_degrees', 'type': 'float64'},
        {'raw': 'precipitation_last_hour_mm', 'alias': 'precipitation_last_hour_mm', 'type': 'float64'},
        {'raw': 'relative_humidity_percent', 'alias': 'relative_humidity_percent', 'type': 'float64'},
        {'raw': 'barometric_pressure_pa', 'alias': 'barometric_pressure_pa', 'type': 'float64'},
        {'raw': 'visibility_miles', 'alias': 'visibility_miles', 'type': 'float64'},
        {'raw': 'conditions', 'alias': 'conditions', 'type': 'string'},
        {'raw': 'ingestion_timestamp', 'alias': 'ingestion_timestamp', 'type': 'timestamp'},
        {'raw': 'ingestion_source', 'alias': 'ingestion_source', 'type': 'string'}
      ]
    }
  } %}
  {% do return(config[source_name]) %}
{% endmacro %}


{% macro get_raw_fields(source_name) %}
  {# Get field config for source #}
  {% set source_config = get_field_config(source_name) %}
  {% set fields = source_config.fields %}
  
  {# Extract just the raw field names #}
  {% set raw_fields = [] %}
  {% for field in fields %}
    {% do raw_fields.append(field.raw) %}
  {% endfor %}
  
  {% do return(raw_fields) %}
{% endmacro %}


{% macro get_unique_key(source_name) %}
  {# Get the unique key configuration for incremental models #}
  {% set source_config = get_field_config(source_name) %}
  {% do return(source_config.unique_key) %}
{% endmacro %}


{% macro get_delete_key_field(source_name) %}
  {# Get the primary delete key field (first field with _id, or first unique_key field) #}
  {% set source_config = get_field_config(source_name) %}
  {% set fields = source_config.fields %}
  
  {# Look for first field with _id in the name #}
  {% for field in fields %}
    {% if '_id' in field.raw.lower() %}
      {% do return(field.raw) %}
    {% endif %}
  {% endfor %}
  
  {# Fallback to first unique_key field #}
  {% do return(source_config.unique_key[0]) %}
{% endmacro %}
