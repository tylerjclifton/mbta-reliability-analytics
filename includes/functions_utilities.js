const {
    schema
} = require('includes/schema');

function getsourceKeys() {
    return Object.keys(schema.fields);
}

function buildDeleteStatement(medallion_layer, source_key) {
    // Get all fields for this source
    const fields = schema.fields[source_key];

    if (!fields || fields.length === 0) {
        throw new Error(`No fields defined for source_key: ${source_key}`);
    }

    // Determine delete key (prefer *_id, fallback *_name)
    const delete_key =
        fields.find(f => f.alias.toLowerCase().includes('_id')) ||
        fields.find(f => f.alias.toLowerCase().includes('_name'));

    if (!delete_key) {
        throw new Error('No valid delete key found within fields');
    }

    // Schema references
    const ds = schema.data_sets;
    const tbl = schema.tables;
    const ingestion_source = schema.meta_data.source;

    let source_data_set, destination_data_set, source_table, destination_table, whereClause;

    switch (medallion_layer) {
        case 'bronze':
            source_data_set = ds.staging;
            destination_data_set = ds.bronze;
            source_table = tbl.staging[source_key];
            destination_table = tbl.bronze[source_key];

            whereClause = `
        ${delete_key.raw} IN (
            SELECT DISTINCT
                ${delete_key.raw}
            FROM ${source_data_set}.${source_table}
        )`;
            break;

        case 'silver':
            source_data_set = ds.bronze;
            destination_data_set = ds.silver;
            source_table = tbl.bronze[source_key];
            destination_table = tbl.silver[source_key];

            whereClause = `
        ${delete_key.alias} IN (
            SELECT DISTINCT
                ${delete_key.raw}
            FROM ${source_data_set}.${source_table}
        )
        AND ${ingestion_source} LIKE '%${source_key}%'`;
            break;

        case 'gold':
            source_data_set = ds.silver;
            destination_data_set = ds.gold;

            // Gold layer is a nested object with sources array
            const goldEntry = tbl.gold[source_key];
            if (!goldEntry) throw new Error(`No gold table defined for ${source_key}`);

            source_table = tbl.silver[source_key];
            destination_table = goldEntry.name || source_key;

            whereClause = `
        ${delete_key.alias} IN (
            SELECT DISTINCT
                ${delete_key.alias}
            FROM ${source_data_set}.${source_table}
        )
        AND ${ingestion_source} LIKE '%${source_key}%'`;
            break;

        default:
            throw new Error('Bad medallion_layer: ' + medallion_layer);
    }

    return `
    DELETE FROM ${destination_data_set}.${destination_table}
    WHERE${whereClause};
    `.trim();
}

module.exports = {
    buildDeleteStatement
};


function getRawFields(source_key) {
    if (!schema || !schema.fields)
        throw new Error('Invalid schema');

    const fieldsArray = schema.fields[source_key];
    if (!fieldsArray)
        throw new Error('Unknown source_key: ' + source_key);

    const raw_fields = fieldsArray.map(d => d.raw);

    return {
        raw_fields
    };
}

function getFinalFields() {
    const sourcesObj = schema.sources;
    const contains = (array, value) => array.includes(value);
    const skip = ['start_date', 'end_date'];

    const finalDimensions = [];
    const finalMetrics = [];
    const finalmeta_data = [];

    let skippedDateRangeField = false;

    Object.values(sourcesObj).forEach(src => {
        (src.dimensions || []).forEach(f => {
            if (skip.includes(f.alias)) {
                skippedDateRangeField = true;
                return;
            }
            if (!contains(finalDimensions, f.alias)) finalDimensions.push(f.alias);
        });
    });

    if (skippedDateRangeField) {
        if (!contains(finalDimensions, 'date')) {
            finalDimensions.unshift('date');
        }
    } else {
        const index = finalDimensions.indexOf('date');
        if (index > 0) {
            finalDimensions.splice(index, 1);
            finalDimensions.unshift('date');
        }
    }

    Object.values(sourcesObj).forEach(src => {
        (src.metrics || []).forEach(f => {
            if (!contains(finalMetrics, f.alias)) finalMetrics.push(f.alias);
        });
    });

    const meta = schema.meta_data || {};
    if (meta.source) finalmeta_data.push(meta.source);
    if (meta.timestamp) finalmeta_data.push(meta.timestamp);

    return {
        finalDimensions,
        finalMetrics,
        finalmeta_data
    };
}

module.exports = {
    getsourceKeys,
    buildDeleteStatement,
    getRawFields,
    getFinalFields
};
