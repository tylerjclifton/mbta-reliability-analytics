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
        'alerts': {
            'key': 'alert_id',
            'dimensions': [{
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
                    'alias': 'route',
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
                    'alias': 'cause',
                    'type': 'STRING'
                },
                {
                    'raw': 'effect',
                    'alias': 'effect',
                    'type': 'STRING'
                },
                {
                    'raw': 'severity',
                    'alias': 'severity',
                    'type': 'INTEGER'
                },
                {
                    'raw': 'lifecycle',
                    'alias': 'lifecycle',
                    'type': 'STRING'
                }
            ]
        },
        'routes': {
            'key': 'route_id',
            'dimensions': [{
                    'raw': 'route_id',
                    'alias': 'route_id',
                    'type': 'STRING'
                },
                {
                    'raw': 'color',
                    'alias': 'color',
                    'type': 'STRING'
                },
                {
                    'raw': 'description',
                    'alias': 'route_description',
                    'type': 'STRING'
                },
                {
                    'raw': 'direction_destination_1',
                    'alias': 'direction_destination_1',
                    'type': 'STRING'
                },
                {
                    'raw': 'direction_destination_2',
                    'alias': 'direction_destination_2',
                    'type': 'STRING'
                },
                {
                    'raw': 'direction_name_1',
                    'alias': 'direction_name_1',
                    'type': 'STRING'
                },
                {
                    'raw': 'direction_name_2',
                    'alias': 'direction_name_2',
                    'type': 'STRING'
                },
                {
                    'raw': 'fare_class',
                    'alias': 'fare_class',
                    'type': 'STRING'
                },
                {
                    'raw': 'long_name',
                    'alias': 'long_name',
                    'type': 'STRING'
                },
                {
                    'raw': 'short_name',
                    'alias': 'short_name',
                    'type': 'STRING'
                },
                {
                    'raw': 'text_color',
                    'alias': 'text_color',
                    'type': 'STRING'
                },
                {
                    'raw': 'type',
                    'alias': 'type',
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
