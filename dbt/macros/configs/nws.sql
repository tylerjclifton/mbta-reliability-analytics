{# 
  NWS Source Configuration
  
  This file contains field definitions as Jinja dictionary that the bronze and 
  silver builders (macros/builders/) use at compile time.
  
  NOTE: A human-readable YAML version exists at models/nws/config_nws.yml
  When updating field definitions, update BOTH files to keep them in sync.
  
  Mirrors the Dataform config.js structure.
#}

{% macro get_partner_field_config(partner, source_name) %}
  {% if partner != 'nws' %}
    {% do return(none) %}
  {% endif %}
  
  {% set config = {
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
        {'raw': 'cloud_base_meters', 'alias': 'cloud_base_meters', 'type': 'float64'},
        {'raw': 'cloud_coverage', 'alias': 'cloud_coverage', 'type': 'string'},
        {'raw': 'conditions', 'alias': 'conditions', 'type': 'string'},
        {'raw': 'ingestion_timestamp', 'alias': 'ingestion_timestamp', 'type': 'timestamp'},
        {'raw': 'ingestion_source', 'alias': 'ingestion_source', 'type': 'string'}
      ]
    }
  } %}
  {% do return(config[source_name]) %}
{% endmacro %}
