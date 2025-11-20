const config = {
    fields: [{
            raw: 'stop_id',
            alias: 'stop_id',
            type: 'STRING'
        },
        {
            raw: 'name',
            alias: 'stop_name',
            type: 'STRING'
        },
        {
            raw: 'municipality',
            alias: 'stop_municipality',
            type: 'STRING'
        },
        {
            raw: 'address',
            alias: 'stop_address',
            type: 'STRING'
        },
        {
            raw: 'latitude',
            alias: 'stop_latitude',
            type: 'STRING'
        },
        {
            raw: 'longitude',
            alias: 'stop_longitude',
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
