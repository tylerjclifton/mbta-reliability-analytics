const alerts = {
    'data_set': 'mbta.',
    'tables': {
        'external': 'external_mbta_alerts',
        'bronze': 'bronze_mbta_alerts_historical',
        's1': 's1_mbta_alerts',
        'gold': 'gold_mbta_alerts'
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
        'etl_fields': [
            'ingestion_datetime',
            'ingestion_source'
        ]
    }
}

module.exports = {
    alerts
}
