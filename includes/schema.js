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
                'raw': 'active_period_start',
                'alias': 'alert_start_date',
                'type': 'DATE'
            },
            {
                'raw': 'active_period_end',
                'alias': 'alert_end_date',
                'type': 'DATE'
            },
            {
                'raw': 'alert_id',
                'alias': 'alert_id',
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
                'raw': 'severity',
                'alias': 'alert_severity',
                'type': 'INTEGER'
            },
            {
                'raw': 'duration_certainty',
                'alias': 'alert_duration_certainty',
                'type': 'STRING'
            },
            {
                'raw': 'created_at',
                'alias': 'alert_created_at',
                'type': 'DATE'
            },
            {
                'raw': 'updated_at',
                'alias': 'alert_updated_at',
                'type': 'DATE'
            },
            {
                'raw': 'ingestion_source',
                'alias': 'ingestion_source',
                'type': 'STRING'
            },
            {
                'raw': 'ingestion_timestamp',
                'alias': 'ingestion_timestamp',
                'type': 'TIMESTAMP'
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
                'raw': 'description',
                'alias': 'route_description',
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
                'raw': 'direction_destinations',
                'alias': 'route_destinations',
                'type': 'STRING'
            },
            {
                'raw': 'direction_names',
                'alias': 'route_directions',
                'type': 'STRING'
            },
            {
                'raw': 'ingestion_source',
                'alias': 'ingestion_source',
                'type': 'STRING'
            },
            {
                'raw': 'ingestion_timestamp',
                'alias': 'ingestion_timestamp',
                'type': 'TIMESTAMP'
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
            },
            {
                'raw': 'ingestion_source',
                'alias': 'ingestion_source',
                'type': 'STRING'
            },
            {
                'raw': 'ingestion_timestamp',
                'alias': 'ingestion_timestamp',
                'type': 'TIMESTAMP'
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
            },
            {
                'raw': 'ingestion_source',
                'alias': 'ingestion_source',
                'type': 'STRING'
            },
            {
                'raw': 'ingestion_timestamp',
                'alias': 'ingestion_timestamp',
                'type': 'TIMESTAMP'
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
    }
}

module.exports = {
    schema
}
