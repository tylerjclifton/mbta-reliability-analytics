const schema = {
    'data_sets': {
        'staging': 'staging',
        'bronze': 'bronze',
        'silver': 'silver',
        'gold': 'gold'
    },
    'tables': {
        'staging': {
            'alerts': 'alerts_raw',
            'routes': 'routes_raw',
            'shapes': 'shapes_raw',
            'stops': 'stops_raw'
        },
        'bronze': {
            'alerts': 'alerts_raw',
            'routes': 'routes_raw',
            'shapes': 'shapes_raw',
            'stops': 'stops_raw'
        },
        'silver': {
            'alerts': 'alerts_cleaned',
            'routes': 'routes_cleaned',
            'shapes': 'shapes_cleaned',
            'stops': 'stops_cleaned'
        },
        'gold': {
            'system_alerts': {
                'name': 'system_alerts',
                'sources': [
                    'alerts',
                    'routes',
                    'stops'
                ]
            }
        }
    },
    'fields': {
        'alerts': [{
                'raw': 'alert_id',
                'alias': 'alert_id',
                'type': 'STRING'
            }, {
                'raw': 'active_period_start',
                'alias': 'alert_start',
                'type': 'TIMESTAMP'
            },
            {
                'raw': 'active_period_end',
                'alias': 'alert_end',
                'type': 'TIMESTAMP'
            },
            {
                'raw': 'duration_certainty',
                'alias': 'alert_duration_certainty',
                'type': 'STRING'
            },
            {
                'raw': 'route',
                'alias': 'route_id',
                'type': 'STRING'
            },
            {
                'raw': 'stop',
                'alias': 'stop_id',
                'type': 'STRING'
            },
            {
                'raw': 'header',
                'alias': 'alert_header',
                'type': 'STRING'
            },
            {
                'raw': 'description',
                'alias': 'alert_description',
                'type': 'STRING'
            },
            {
                'raw': 'cause',
                'alias': 'alert_cause',
                'type': 'STRING'
            },
            {
                'raw': 'effect',
                'alias': 'alert_effect',
                'type': 'STRING'
            },
            {
                'raw': 'service_effect',
                'alias': 'alert_service_effect',
                'type': 'STRING'
            },
            {
                'raw': 'severity',
                'alias': 'alert_severity',
                'type': 'INTEGER'
            },
            {
                'raw': 'lifecycle',
                'alias': 'alert_lifecycle',
                'type': 'STRING'
            },
            {
                'raw': 'created_at',
                'alias': 'alert_created_at',
                'type': 'STRING'
            },
            {
                'raw': 'updated_at',
                'alias': 'alert_updated_at',
                'type': 'STRING'
            }
        ],
        'routes': [{
                'raw': 'route_id',
                'alias': 'route_id',
                'type': 'STRING'
            },
            {
                'raw': 'long_name',
                'alias': 'route_name',
                'type': 'STRING'
            },
            {
                'raw': 'route_type',
                'alias': 'route_type',
                'type': 'STRING'
            },
            {
                'raw': 'color',
                'alias': 'route_color',
                'type': 'STRING'
            },
            {
                'raw': 'description',
                'alias': 'route_description',
                'type': 'STRING'
            },
            {
                'raw': 'direction_destinations',
                'alias': 'route_destinations',
                'type': 'STRING'
            },
            {
                'raw': 'direction_names',
                'alias': 'route_directions',
                'type': 'STRING'
            }
        ],
        'shapes': [{
                'raw': 'shape_id',
                'alias': 'shape_id',
                'type': 'STRING'
            },
            {
                'raw': 'polyline',
                'alias': 'shape_polyline',
                'type': 'STRING'
            }
        ],
        'stops': [{
                'raw': 'stop_id',
                'alias': 'stop_id',
                'type': 'STRING'
            },
            {
                'raw': 'name',
                'alias': 'stop_name',
                'type': 'STRING'
            },
            {
                'raw': 'description',
                'alias': 'stop_description',
                'type': 'STRING'
            },
            {
                'raw': 'municipality',
                'alias': 'stop_municipality',
                'type': 'STRING'
            },
            {
                'raw': 'latitude',
                'alias': 'stop_latitude',
                'type': 'STRING'
            },
            {
                'raw': 'longitude',
                'alias': 'stop_longitude',
                'type': 'STRING'
            }
        ]
    },
    'taxonomy': {
        'routes': {
            'route_type': {
                '0': 'Light Rail',
                '1': 'Heavy Rail'
            }
        }
    },
    'meta_data': {
        'source': 'ingestion_source',
        'timestamp': 'ingestion_timestamp'
    }
}

module.exports = {
    schema
}
