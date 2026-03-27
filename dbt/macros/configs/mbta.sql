{# 
  MBTA Source Configuration
  
  This file contains field definitions as Jinja dictionary that the bronze and 
  silver builders (macros/builders/) use at compile time.
  
  NOTE: A human-readable YAML version exists at models/mbta/config_mbta.yml
  When updating field definitions, update BOTH files to keep them in sync.
  
  Mirrors the Dataform config.js structure.
#}

{% macro get_partner_field_config(partner, source_name) %}
  {% if partner != 'mbta' %}
    {% do return(none) %}
  {% endif %}
  
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
    }
  } %}
  {% do return(config[source_name]) %}
{% endmacro %}
