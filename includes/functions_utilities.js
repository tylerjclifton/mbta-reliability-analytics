// Import schema
const {
    schema
} = require('includes/schema');

// Get raw values from fields array
function getRawFields(source_key) {

    // Throw error if schema does not exist or does not have nested fields object
    if (!schema || !schema.fields) {
        throw new Error('Invalid schema');
    }

    // Get source fields array
    const fields_array = schema.fields[source_key];

    // Throw error if fields array does not exist or is empty
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

    // Get data set and table info
    const data_sets = schema.data_sets;
    const tables = schema.tables;

    // Initialize data set and table variables
    let source_data_set, destination_data_set, source_table, destination_table;

    // Initialize delete key variable
    let delete_key;

    switch (medallion_layer) {

        // When medallion layer is bronze
        case 'bronze': {

            // Get source fields array
            const fields_array = schema.fields[source_key];

            // Throw error if fields array does not exist
            if (!fields_array || !fields_array.length) {
                throw new Error(`No fields defined for source: ${source_key}`);
            }

            // Determine delete key (prefer *_id, fallback *_name)
            delete_key =
                fields_array.find(field => field.alias.toLowerCase().includes('_id')) ||
                fields_array.find(field => field.alias.toLowerCase().includes('_name'));

            // Throw error if no valid delete key exists
            if (!delete_key) {
                throw new Error('No valid delete key found within fields');
            }

            // Get source data set and table
            source_data_set = data_sets.staging;
            source_table = tables.staging[source_key];

            // Get destination data set and table
            destination_data_set = data_sets.bronze;
            destination_table = tables.bronze[source_key];

            // Break out of switch
            break;

        }

        // When medallion layer is silver
        case 'silver': {

            // Get fields array for source
            const fields_array = schema.fields[source_key];

            // Throw error if fields array does not exist
            if (!fields_array || !fields_array.length) {
                throw new Error(`No fields defined for source: ${source_key}`);
            }

            // Determine delete key (prefer *_id, fallback *_name)
            delete_key =
                fields_array.find(f => f.alias.toLowerCase().includes('_id')) ||
                fields_array.find(f => f.alias.toLowerCase().includes('_name'));

            // Throw error if no valid delete key exists
            if (!delete_key) {
                throw new Error('No valid delete key found within fields');
            }

            // Get source data set and table
            source_data_set = data_sets.bronze;
            source_table = tables.bronze[source_key];

            // Get destination data set and table
            destination_data_set = data_sets.silver;
            destination_table = tables.silver[source_key];

            // Break out of switch
            break;

        }

        // When medallion layer is gold
        case 'gold': {

            // Get gold table info
            const gold_table = tables.gold[source_key];

            // Throw error if gold table does not exist
            if (!gold_table) {
                throw new Error(`Gold table not found: ${source_key}`);
            }

            // Get primary source for gold table
            primary_source = schema.tables.gold[source_key].sources[0];

            // Create array to hold combined fields
            const combined_fields = [];

            // Create set to hold previously seen fields
            const seen_aliases = new Set();

            // Iterate through listed sources for gold table
            gold_table.sources.forEach(src => {

                // Get source fields array
                const fields_array = schema.fields[src];

                // Throw error if fields array does not exist
                if (!fields_array || !fields_array.length) {
                    throw new Error(`No fields defined for source: ${source_key}`);
                }

                // Iterate through each field in fields array
                fields_array.forEach(field => {

                    // If field's alias value has not been seen yet
                    if (!seen_aliases.has(field.alias)) {

                        // Add field to combined fields array
                        combined_fields.push(field);

                        // Add field to seen aliases array
                        seen_aliases.add(field.alias);

                    }

                });

            });

            // Determine delete key (prefer *_id, fallback *_name) from combined fields
            delete_key =
                combined_fields.find(f => f.alias.toLowerCase().includes('_id')) ||
                combined_fields.find(f => f.alias.toLowerCase().includes('_name'));

            // Throw error if no valid delete key exists
            if (!delete_key) {
                throw new Error('No valid delete key found within fields');
            }

            // Get source data set and table
            source_data_set = data_sets.silver;
            source_table = tables.silver[gold_table.sources[0]]; // Use first source for delete reference

            // Get destination data set and table
            destination_data_set = data_sets.gold;
            destination_table = gold_table.name;

            // Break out of switch
            break;

        }

        // When no valid medallion layer is provided throw error
        default:
            throw new Error('Bad medallion_layer: ' + medallion_layer);
    }

    // Build where clause for delete statement
    const whereClause =

        // Check if medallion layer is bronze or silver
        medallion_layer === 'bronze' ?

        // If bronze
        `
        ${delete_key.raw} IN (
            SELECT DISTINCT
                ${delete_key.raw}
            FROM ${source_data_set}.${source_table}
        )
        `
        // Or
        :
        // If not bronze
        `
        ${delete_key.alias} IN (
            SELECT DISTINCT
                ${delete_key.alias}
            FROM ${source_data_set}.${source_table}
        )
        `

    // Return delete statement
    return `
    DELETE FROM ${destination_data_set}.${destination_table}
    WHERE${whereClause};
    `

}

// Export necessary function(s)
module.exports = {
    getRawFields,
    buildDeleteStatement
};
