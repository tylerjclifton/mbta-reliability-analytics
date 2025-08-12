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
                    'rawName': 'alert_start',
                    'newName': 'alert_start',
                    'dataType': 'TIMESTAMP'
                },
                {
                    'rawName': 'alert_end',
                    'newName': 'alert_end',
                    'dataType': 'TIMESTAMP'
                },
                {
                    'rawName': 'alert_id',
                    'newName': 'alert_id',
                    'dataType': 'STRING'
                },
                {
                    'rawName': 'route',
                    'newName': 'route',
                    'dataType': 'STRING'
                },
                {
                    'rawName': 'header',
                    'newName': 'alert_header',
                    'dataType': 'STRING'
                },
                {
                    'rawName': 'description',
                    'newName': 'alert_description',
                    'dataType': 'STRING'
                },
                {
                    'rawName': 'cause',
                    'newName': 'cause',
                    'dataType': 'STRING'
                },
                {
                    'rawName': 'effect',
                    'newName': 'effect',
                    'dataType': 'STRING'
                },
                {
                    'rawName': 'severity',
                    'newName': 'severity',
                    'dataType': 'INTEGER'
                },
                {
                    'rawName': 'lifecycle',
                    'newName': 'lifecycle',
                    'dataType': 'STRING'
                }
            ]
        },
        'routes': {
            'key': 'route_id',
            'dimensions': [{
                    'rawName': 'route_id',
                    'newName': 'route_id',
                    'dataType': 'TIMESTAMP'
                },
                {
                    'rawName': 'color',
                    'newName': 'color',
                    'dataType': 'TIMESTAMP'
                },
                {
                    'rawName': 'description',
                    'newName': 'route_description',
                    'dataType': 'STRING'
                },
                {
                    'rawName': 'direction_destination_1',
                    'newName': 'direction_destination_1',
                    'dataType': 'STRING'
                },
                {
                    'rawName': 'direction_destination_2',
                    'newName': 'direction_destination_2',
                    'dataType': 'STRING'
                },
                {
                    'rawName': 'direction_name_1',
                    'newName': 'direction_name_1',
                    'dataType': 'STRING'
                },
                {
                    'rawName': 'direction_name_2',
                    'newName': 'direction_name_2',
                    'dataType': 'STRING'
                },
                {
                    'rawName': 'fare_class',
                    'newName': 'fare_class',
                    'dataType': 'STRING'
                },
                {
                    'rawName': 'long_name',
                    'newName': 'long_name',
                    'dataType': 'INTEGER'
                },
                {
                    'rawName': 'short_name',
                    'newName': 'short_name',
                    'dataType': 'STRING'
                },
                {
                    'rawName': 'text_color',
                    'newName': 'text_color',
                    'dataType': 'INTEGER'
                },
                {
                    'rawName': 'type',
                    'newName': 'type',
                    'dataType': 'STRING'
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
