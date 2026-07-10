{% macro get_mbta_config() %}

  {% set config = {
    'sources': {
      'alerts': {
        'staging': {
          'dataset': 'staging',
          'table': 'mbta_alerts',
        },
        'grain_keys': ['alert_id', 'route'],
        'fields': [
          {
            'raw': 'alert_id',
            'alias': 'alert_id',
            'type': 'string'
          },
          {
            'raw': 'route',
            'alias': 'route_id',
            'type': 'string'
          },
          {
            'raw': 'active_period_start',
            'alias': 'alert_start_date',
            'type': 'date'
          },
          {
            'raw': 'active_period_end',
            'alias': 'alert_end_date',
            'type': 'date'
          },
          {
            'raw': 'header',
            'alias': 'alert_header',
            'type': 'string'
          },
          {
            'raw': 'description',
            'alias': 'alert_description',
            'type': 'string'
          },
          {
            'raw': 'cause',
            'alias': 'alert_cause',
            'type': 'string'
          },
          {
            'raw': 'effect',
            'alias': 'alert_effect',
            'type': 'string'
          },
          {
            'raw': 'severity',
            'alias': 'alert_severity',
            'type': 'int64'
          },
          {
            'raw': 'duration_certainty',
            'alias': 'alert_duration_certainty',
            'type': 'string'
          },
          {
            'raw': 'created_at',
            'alias': 'alert_created_at',
            'type': 'date'
          },
          {
            'raw': 'updated_at',
            'alias': 'alert_updated_at',
            'type': 'date'
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
      },
      'ridership': {
        'staging': {
          'dataset': 'staging',
          'table': 'mbta_ridership',
        },
        'grain_keys': ['service_date', 'route_or_line'],
        'fields': [
          {
            'raw': 'service_date',
            'alias': 'service_date',
            'type': 'date'
          },
          {
            'raw': 'route_or_line',
            'alias': 'route_name',
            'type': 'string'
          },
          {
            'raw': 'total_gated_entries',
            'alias': 'ridership',
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
      },
      'routes': {
        'staging': {
          'dataset': 'staging',
          'table': 'mbta_routes',
        },
        'grain_keys': ['route_id'],
        'fields': [
          {
            'raw': 'route_id',
            'alias': 'route_id',
            'type': 'string'
          },
          {
            'raw': 'long_name',
            'alias': 'route_name',
            'type': 'string'
          },
          {
            'raw': 'description',
            'alias': 'route_description',
            'type': 'string'
          },
          {
            'raw': 'route_type',
            'alias': 'route_type',
            'type': 'string'
          },
          {
            'raw': 'color',
            'alias': 'route_color',
            'type': 'string'
          },
          {
            'raw': 'direction_destinations',
            'alias': 'route_destinations',
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
        ]
      }
    }
  } %}
  {% do return(config) %}
{% endmacro %}

            {
              'raw': 'alert_id',
              'alias': 'alert_id',
              'type': 'string'
            },
            {
              'raw': 'route',
              'alias': 'route_id',
              'type': 'string'
            },
            {
              'raw': 'active_period_start',
              'alias': 'alert_start_date',
              'type': 'date'
            },
            {
              'raw': 'active_period_end',
              'alias': 'alert_end_date',
              'type': 'date'
            },
            {
              'raw': 'header',
              'alias': 'alert_header',
              'type': 'string'
            },
            {
              'raw': 'description',
              'alias': 'alert_description',
              'type': 'string'
            },
            {
              'raw': 'cause',
              'alias': 'alert_cause',
              'type': 'string'
            },
            {
              'raw': 'effect',
              'alias': 'alert_effect',
              'type': 'string'
            },
            {
              'raw': 'severity',
              'alias': 'alert_severity',
              'type': 'int64'
            },
            {
              'raw': 'duration_certainty',
              'alias': 'alert_duration_certainty',
              'type': 'string'
            },
            {
              'raw': 'created_at',
              'alias': 'alert_created_at',
              'type': 'date'
            },
            {
              'raw': 'updated_at',
              'alias': 'alert_updated_at',
              'type': 'date'
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
      },
      'ridership': {
        'staging': {
          'dataset': 'staging',
          'table': 'mbta_ridership',
        },
        'grain_keys': ['service_date', 'route_or_line'],
        'fields': {
          'dimensions': [
            {
              'raw': 'service_date',
              'alias': 'service_date',
              'type': 'date'
            },
            {
              'raw': 'route_or_line',
              'alias': 'route_name',
              'type': 'string'
            },
            {
              'raw': 'total_gated_entries',
              'alias': 'ridership',
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
      },
      'routes': {
        'staging': {
          'dataset': 'staging',
          'table': 'mbta_routes',
        },
        'grain_keys': ['route_id'],
        'fields': {
          'dimensions': [
            {
              'raw': 'route_id',
              'alias': 'route_id',
              'type': 'string'
            },
            {
              'raw': 'long_name',
              'alias': 'route_name',
              'type': 'string'
            },
            {
              'raw': 'description',
              'alias': 'route_description',
              'type': 'string'
            },
            {
              'raw': 'route_type',
              'alias': 'route_type',
              'type': 'string'
            },
            {
              'raw': 'color',
              'alias': 'route_color',
              'type': 'string'
            },
            {
              'raw': 'direction_destinations',
              'alias': 'route_destinations',
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
          ]
        }
      }
    }
  } %}
  {% do return(config) %}
{% endmacro %}
