// Import schema
const {
    schema
} = require('includes/schema');

// Get raw values from fields array
function getRawFields(source_key) {

    // Throw error if schema doesn't exist or does not have nested fields object
    if (!schema || !schema.fields) {
        throw new Error('Invalid schema');
    }

    // Get source's fields array
    const fields_array = schema.fields[source_key];

    // Throw error if fields array doesn't exist or is empty
    if (!fields_array || fields_array.length === 0) {
        throw new Error(`No fields defined for source: ${source_key}`);
    }

    // Extract raw value from each field in fields array
    const raw_fields = fields_array.map(field => field.raw);

    // Return raw fields
    return {
        raw_fields
    };

}

// Build delete statement for any medallion layer (bronze, silver, gold)
function buildDeleteStatement(medallion_layer, source_key) {
    const ds = schema.data_sets;
    const tbl = schema.tables;
    const ingestion_source = schema.meta_data.source;

    let source_data_set, destination_data_set, source_table, destination_table;
    let delete_key;

    switch (medallion_layer) {
        case 'bronze': {
            const fields = schema.fields[source_key];
            if (!fields || !fields.length) throw new Error(`No fields defined for source: ${source_key}`);

            delete_key =
                fields.find(f => f.alias.toLowerCase().includes('_id')) ||
                fields.find(f => f.alias.toLowerCase().includes('_name'));
            if (!delete_key) throw new Error('No valid delete key found within fields');

            source_data_set = ds.staging;
            destination_data_set = ds.bronze;
            source_table = tbl.staging[source_key];
            destination_table = tbl.bronze[source_key];
            break;
        }

        case 'silver': {
            const fields = schema.fields[source_key];
            if (!fields || !fields.length) throw new Error(`No fields defined for source: ${source_key}`);

            delete_key =
                fields.find(f => f.alias.toLowerCase().includes('_id')) ||
                fields.find(f => f.alias.toLowerCase().includes('_name'));
            if (!delete_key) throw new Error('No valid delete key found within fields');

            source_data_set = ds.bronze;
            destination_data_set = ds.silver;
            source_table = tbl.bronze[source_key];
            destination_table = tbl.silver[source_key];
            break;
        }

        case 'gold': {
            const goldEntry = tbl.gold[source_key];
            if (!goldEntry) throw new Error(`No gold table defined for ${source_key}`);

            // Combine fields from all sources
            const combinedFields = [];
            const seenAliases = new Set();

            goldEntry.sources.forEach(src => {
                const srcFields = schema.fields[src];
                if (!srcFields) throw new Error(`No fields defined for source: ${src}`);
                srcFields.forEach(f => {
                    if (!seenAliases.has(f.alias)) {
                        combinedFields.push(f);
                        seenAliases.add(f.alias);
                    }
                });
            });

            delete_key =
                combinedFields.find(f => f.alias.toLowerCase().includes('_id')) ||
                combinedFields.find(f => f.alias.toLowerCase().includes('_name'));
            if (!delete_key) throw new Error('No valid delete key found within combined fields');

            source_data_set = ds.silver;
            destination_data_set = ds.gold;
            source_table = tbl.silver[goldEntry.sources[0]];
            destination_table = goldEntry.name || source_key;
            break;
        }

        default:
            throw new Error('Bad medallion_layer: ' + medallion_layer);
    }

    const whereClause =
        medallion_layer === 'bronze' ?
        `\n${delete_key.raw} IN (SELECT DISTINCT ${delete_key.raw} FROM ${source_data_set}.${source_table})` :
        `\n${delete_key.alias} IN (SELECT DISTINCT ${delete_key.raw} FROM ${source_data_set}.${source_table})` +
        (medallion_layer === 'gold' ? '' : `\nAND ${ingestion_source} LIKE '%${source_key}%'`);

    return `
DELETE FROM ${destination_data_set}.${destination_table}
WHERE${whereClause};
`.trim();
}

module.exports = {
    buildDeleteStatement
};


// Export necessary function(s)
module.exports = {
    buildDeleteStatement,
    getRawFields
};
