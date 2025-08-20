const schemaMap = {
    'dataSets': {
        'staging': 'staging',
        'bronze': 'bronze',
        'silver': 'silver',
        'gold': 'gold'
    },
    'tables': {
        'staging': {
            'alerts': 'alerts_staging',
            'routes': 'routes_staging'
        },
        'bronze': {
            'alerts': 'alerts_raw',
            'routes': 'routes_raw'
        },
        'silver': {
            'alerts': 'alerts_enhanced'
        },
        'gold': {
            'alerts': 'system_alerts'
        }
    },
    'fields': {
        'keys': {
            'alerts': 'alert_id',
            'routes': 'route_id'
        },
        'dimensions': {
            'alerts': [{
                    'raw': 'alert_start',
                    'alias': 'alert_start',
                    'type': 'TIMESTAMP'
                },
                {
                    'raw': 'alert_end',
                    'alias': 'alert_end',
                    'type': 'TIMESTAMP'
                },
                {
                    'raw': 'alert_id',
                    'alias': 'alert_id',
                    'type': 'STRING'
                },
                {
                    'raw': 'route',
                    'alias': 'alert_route',
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
                    'raw': 'lifecycle',
                    'alias': 'alert_lifecycle',
                    'type': 'STRING'
                }
            ],
            'routes': [{
                    'raw': 'route_id',
                    'alias': 'route_id',
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
                    'raw': 'direction_destination_1',
                    'alias': 'route_direction_destination_1',
                    'type': 'STRING'
                },
                {
                    'raw': 'direction_destination_2',
                    'alias': 'route_direction_destination_2',
                    'type': 'STRING'
                },
                {
                    'raw': 'direction_name_1',
                    'alias': 'route_direction_name_1',
                    'type': 'STRING'
                },
                {
                    'raw': 'direction_name_2',
                    'alias': 'route_direction_name_2',
                    'type': 'STRING'
                },
                {
                    'raw': 'fare_class',
                    'alias': 'route_fare_class',
                    'type': 'STRING'
                },
                {
                    'raw': 'long_name',
                    'alias': 'route_long_name',
                    'type': 'STRING'
                },
                {
                    'raw': 'short_name',
                    'alias': 'route_short_name',
                    'type': 'STRING'
                },
                {
                    'raw': 'text_color',
                    'alias': 'route_text_color',
                    'type': 'STRING'
                },
                {
                    'raw': 'type',
                    'alias': 'route_type',
                    'type': 'STRING'
                }
            ]
        },
        'ingestion': {
            'source': 'ingestion_source',
            'timestamp': 'ingestion_timestamp'
        }
    }
}

module.exports = {
    schemaMap
}
