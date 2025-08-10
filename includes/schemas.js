const schemaMap = {
    'dataSet': 'mbta',
    'tables': {
        'external': {
            'alerts': 'external_alerts',
            'routes': 'external_routes'
        },
        'bronze': {
            'alerts': 'bronze_alerts',
            'routes': 'bronze_routes'
        },
        'silver': {
            's1': 's1_route_alerts'
        },
        'gold': {
            'route_alerts': 'gold_route_alerts'
        }
    },
    'fields': {
        'alerts': {
            'key': 'alert_id',
            'dimensions': [{
                    'alert_start': 'TIMESTAMP'
                },
                {
                    'alert_end': 'TIMESTAMP'
                },
                {
                    'alert_id': 'STRING'
                },
                {
                    'route': 'STRING'
                },
                {
                    'header': 'STRING'
                },
                {
                    'description': 'STRING'
                },
                {
                    'cause': 'STRING'
                },
                {
                    'effect': 'STRING'
                },
                {
                    'severity': 'INTEGER'
                },
                {
                    'lifecycle': 'STRING'
                }
            ]
        },
        'routes': {
            'key': 'route_id',
            'dimensions': [{
                    'route_id': 'STRING'
                },
                {
                    'color': 'STRING'
                },
                {
                    'description': 'STRING'
                },
                {
                    'direction_destination_1': 'STRING'
                },
                {
                    'direction_destination_2': 'STRING'
                },
                {
                    'direction_name_1': 'STRING'
                },
                {
                    'direction_name_2': 'STRING'
                },
                {
                    'fare_class': 'STRING'
                },
                {
                    'long_name': 'STRING'
                },
                {
                    'short_name': 'STRING'
                },
                {
                    'text_color': 'STRING'
                },
                {
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
