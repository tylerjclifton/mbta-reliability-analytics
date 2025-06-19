const alerts = {
    'dataSet': 'mbta',
    'tables': {
        'external': 'external_alerts',
        'bronze': 'bronze_alerts',
        'gold': 'gold_alerts'
    },
    'fields': {
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
        ],
        'ingestionInfo': [
            'ingestion_datetime',
            'ingestion_source'
        ]
    }
}

const routes = {
    'dataSet': 'mbta',
    'tables': {
        'external': 'external_routes',
        'bronze': 'bronze_routes',
        'gold': 'gold_routes'
    },
    'fields': {
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
            'short_name',
            'sort_order',
            'text_color',
            'links',
            'agency_id',
            'agency_type',
            'line_id',
            'line_type'
        ],
        'ingestionInfo': [
            'ingestion_datetime',
            'ingestion_source'
        ]
    }
}

module.exports = {
    alerts,
    routes
}
