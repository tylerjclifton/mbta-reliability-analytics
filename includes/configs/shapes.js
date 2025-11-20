const config = {
    fields: [{
            raw: 'shape_id',
            alias: 'shape_id',
            type: 'STRING'
        },
        {
            raw: 'polyline',
            alias: 'shape_polyline',
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
