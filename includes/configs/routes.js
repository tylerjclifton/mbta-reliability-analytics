const config = {
    fields: [{
            raw: 'route_id',
            alias: 'route_id',
            type: 'STRING'
        },
        {
            raw: 'long_name',
            alias: 'route_name',
            type: 'STRING'
        },
        {
            raw: 'description',
            alias: 'route_description',
            type: 'STRING'
        },
        {
            raw: 'route_type',
            alias: 'route_type',
            type: 'STRING'
        },
        {
            raw: 'color',
            alias: 'route_color',
            type: 'STRING'
        },
        {
            raw: 'direction_destinations',
            alias: 'route_destinations',
            type: 'STRING'
        },
        {
            raw: 'ingestion_timestamp',
            alias: 'ingestion_timestamp',
            type: 'TIMESTAMP'
        },
        {
            raw: 'ingestion_source',
            alias: 'ingestion_source',
            type: 'STRING'
        }
    ]
}

module.exports = {
    config
}
