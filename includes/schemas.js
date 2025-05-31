const alerts = {
    'dataSet': 'mbta.',
    'tables': {
        'external': 'external_alerts',
        'bronze': 'bronze_alerts'
    },
    'fields': {
        'key': 'id',
        'dates': [
            'alert_start',
            'alert_end'
        ],
        'dimensions': [
            'routes',
            'id',
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

module.exports = {
    alerts
}
