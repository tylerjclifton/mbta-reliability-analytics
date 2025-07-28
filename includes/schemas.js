const schemaMap = {
    'dataSets': 'mbta',
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
            's1': 's1_route_alerts',
            's2': 's2_route_alerts'
        },
        'gold': 'gold_route_alerts'
    },
    'fields': {
        'alerts': {
            'key': 'id',
            'dimensions': [
                'alert_start',
                'alert_end',
                'id',
                'route',
                'header',
                'description',
                'cause',
                'effect',
                'severity',
                'lifecycle'
            ]
        },
        'routes': {
            'key': 'id',
            'dimensions': [
                'id',
                'color',
                'description',
                'direction_destination_1',
                'direction_destination_2',
                'direction_name_1',
                'direction_name_2',
                'fare_class',
                'long_name',
                'links',
            ]
        }
    }
}
module.exports = {
    schemaMap
}
