{% macro get_nws_config() %}

  {% set config = {
    'sources': {
      'weather': {
        'lookup': false,
        'staging': {
          'dataset': 'staging',
          'table': 'nws_weather',
        },
        'grain_keys': ['observation_timestamp', 'station_id'],
        'fields': {
          'dimensions': [
            {
              'raw': 'observation_timestamp',
              'alias': 'observation_timestamp',
              'type': 'timestamp'
            },
            {
              'raw': 'station_id',
              'alias': 'station_id',
              'type': 'string'
            },
            {
              'raw': 'temperature_fahrenheit',
              'alias': 'temperature_fahrenheit',
              'type': 'float64'
            },
            {
              'raw': 'temperature_celsius',
              'alias': 'temperature_celsius',
              'type': 'float64'
            },
            {
              'raw': 'dewpoint_fahrenheit',
              'alias': 'dewpoint_fahrenheit',
              'type': 'float64'
            },
            {
              'raw': 'dewpoint_celsius',
              'alias': 'dewpoint_celsius',
              'type': 'float64'
            },
            {
              'raw': 'wind_speed_mph',
              'alias': 'wind_speed_mph',
              'type': 'float64'
            },
            {
              'raw': 'wind_direction_degrees',
              'alias': 'wind_direction_degrees',
              'type': 'float64'
            },
            {
              'raw': 'precipitation_last_hour_mm',
              'alias': 'precipitation_last_hour_mm',
              'type': 'float64'
            },
            {
              'raw': 'relative_humidity_percent',
              'alias': 'relative_humidity_percent',
              'type': 'float64'
            },
            {
              'raw': 'barometric_pressure_pa',
              'alias': 'barometric_pressure_pa',
              'type': 'float64'
            },
            {
              'raw': 'visibility_miles',
              'alias': 'visibility_miles',
              'type': 'float64'
            },
            {
              'raw': 'cloud_base_meters',
              'alias': 'cloud_base_meters',
              'type': 'float64'
            },
            {
              'raw': 'cloud_coverage',
              'alias': 'cloud_coverage',
              'type': 'string'
            },
            {
              'raw': 'conditions',
              'alias': 'conditions',
              'type': 'string'
            },
            {
              'raw': 'ingestion_timestamp',
              'alias': 'ingestion_timestamp',
              'type': 'timestamp'
            },
            {
              'raw': 'ingestion_source',
              'alias': 'ingestion_source',
              'type': 'string'
            }
          ],
          'metrics': []
        }
      }
    },
    'joins': []
  } %}
  {% do return(config) %}
{% endmacro %}
