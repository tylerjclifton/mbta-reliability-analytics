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

// Build delete statement
function buildDeleteStatement(medallion_layer, source_key) {

    // Get source's fields array
    const fields_array = schema.fields[source_key];

    // Throw error if fields array doesn't exist or is empty
    if (!fields_array || fields_array.length === 0) {
        throw new Error(`No fields defined for source: ${source_key}`);
    }

    // Determine delete key (prefer *_id, fallback *_name)
    const delete_key =
        fields_array.find(f => f.alias.toLowerCase().includes('_id')) ||
        fields_array.find(f => f.alias.toLowerCase().includes('_name'));

    // Throw error if no valid delete key is in fields array
    if (!delete_key) {
        throw new Error('No valid delete key found within fields');
    }

    // Schema references
    const data_sets = schema.data_sets;
    const tables = schema.tables;
    const ingestion_source = schema.meta_data.source;

    // Initialize variables for database references and SQL components
    let source_data_set, destination_data_set, source_table, destination_table, where_clause;

    switch (medallion_layer) {

        // When medallion layer is bronze
        case 'bronze':

            // Get source data set and table
            source_data_set = data_sets.staging;
            source_table = tables.staging[source_key];

            // Get destination data set and table
            destination_data_set = data_sets.bronze;
            destination_table = tables.bronze[source_key];

            // Delete records that exist in staging (using raw field names for staging)
            where_clause = `
    ${delete_key.raw} IN (
        SELECT DISTINCT
            ${delete_key.raw}
        FROM ${source_data_set}.${source_table}
    )`;
            break;

            // When medallion layer is silver
        case 'silver':

            // Get source data set and table
            source_data_set = data_sets.bronze;
            source_table = tables.bronze[source_key];

            // Get destination data set and table
            destination_data_set = data_sets.silver;
            destination_table = tables.silver[source_key];

            // Delete records using alias field names (silver uses cleaned field names)
            // Also filter by ingestion source to only delete records from this specific source
            where_clause = `
    ${delete_key.alias} IN (
        SELECT DISTINCT
            ${delete_key.raw}
        FROM ${source_data_set}.${source_table}
    )
    AND ${ingestion_source} LIKE '%${source_key}%'`;
            break;

            // When medallion layer is gold
        case 'gold':

            // Get source and destination data sets
            source_data_set = data_sets.silver;
            destination_data_set = data_sets.gold;

            // Get the gold table configuration which contains multiple source references
            const gold_entry = tables.gold[source_key];

            // Throw error if no valid gold table exists
            if (!gold_entry) {
                throw new Error(`No gold table defined for ${source_key}`);
            }

            // Combine field definitions from ALL sources listed in the gold table
            // This creates a master list of all possible fields across sources
            const combined_fields = [];

            // Track which field aliases we have already added
            const seen_aliases = new Set();

            // Iterate through each source listed in gold sources section
            gold_entry.sources.forEach(src => {

                // Get fields array for current source
                const fields_array = schema.fields[src];

                // If fields
                if (fields_array) {
                    fields_array.forEach(field => {

                        // Only add each unique alias once (prevents duplicates like route_id appearing twice)
                        if (!seen_aliases.has(field.alias)) {
                            combined_fields.push(field);
                            seen_aliases.add(field.alias);
                        }
                    });
                }
            });

            // Find delete key from the combined field list (prefer _id fields, fallback to _name fields)
            delete_key = combined_fields.find(f => f.alias.toLowerCase().includes('_id')) ||
                combined_fields.find(f => f.alias.toLowerCase().includes('_name'));

            // Throw error if no valid delete key is in combined fields array
            if (!delete_key) {
                throw new Error('No valid delete key found within combined fields');
            }

            // Use the first source as the reference table for the WHERE clause
            source_table = tables.silver[gold_entry.sources[0]];
            destination_table = gold_entry.name || source_key;

            // Delete records from gold table that exist in the primary source
            // Filter by ingestion source from the first source only
            where_clause = `
    ${delete_key.alias} IN (
        SELECT DISTINCT
            ${delete_key.alias}
        FROM ${source_data_set}.${source_table}
    )
    AND ${ingestion_source} LIKE '%${gold_entry.sources[0]}%'`;
            break;

            // Throw error if provided medallion layer does not exist
        default:
            throw new Error('Bad medallion_layer: ' + medallion_layer);
    }

    // Return delete statement
    return `
DELETE FROM ${destination_data_set}.${destination_table}
WHERE${where_clause};
`;

}

// Export necessary function(s)
module.exports = {
    buildDeleteStatement,
    getRawFields
};
