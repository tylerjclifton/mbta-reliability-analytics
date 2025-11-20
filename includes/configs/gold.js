const config = {
    tables: {
        rail_alerts: {
            name: 'rail_alerts',
            sources: [
                'alerts',
                'routes',
                'stops'
            ]
        }
    }
}

module.exports = {
    config
}
