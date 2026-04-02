{% macro get_mbta_config() %}
  
  {% set config = {
    'sources': {
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
    }
  },
  'joins': [
        {
          'source': 'routes',
          'join_type': 'left',
          'on': [{'left': 'route_id', 'right': 'route_id'}]
        }
      ]
  } %}
  {% do return(config) %}
{% endmacro %}
