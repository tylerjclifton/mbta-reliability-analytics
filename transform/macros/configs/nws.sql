{% macro get_nws_config() %}

  {% set config = {
    'sources': {
      'weather': {
        'staging': {
          'dataset': 'stage',
          'table': 'nws_weather',
        },
        'grain_keys': ['observation_date', 'station_id'],
        'fields': [
          {
            'raw': 'observation_date',
            'alias': 'observation_date',
            'type': 'date'
          },
          {
            'raw': 'station_id',
            'alias': 'station_id',
            'type': 'string'
          },
          {
            'raw': 'avg_temperature_f',
            'alias': 'avg_temperature_f',
            'type': 'float64'
          },
          {
            'raw': 'max_temperature_f',
            'alias': 'max_temperature_f',
            'type': 'float64'
          },
          {
            'raw': 'total_precipitation_mm',
            'alias': 'total_precipitation_mm',
            'type': 'float64'
          },
          {
            'raw': 'avg_wind_speed_mph',
            'alias': 'avg_wind_speed_mph',
            'type': 'float64'
          },
          {
            'raw': 'avg_humidity_percent',
            'alias': 'avg_humidity_percent',
            'type': 'float64'
          },
          {
            'raw': 'min_visibility_miles',
            'alias': 'min_visibility_miles',
            'type': 'float64'
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
        ]
      }
    }
  } %}
  {% do return(config) %}
{% endmacro %}
