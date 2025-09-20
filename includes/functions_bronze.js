// Import schema
const {
    schema
} = require('includes/schema');

// Build desert statement for bronze layer
function buildDesertBronze(source_key) {

    // Get source data set and table
    const source_data_set = schema.data_sets.staging;
    const source_table = schema.tables.staging[source_key];

    // Get raw values from source's fields array
    const {
        raw_fields
    } = functions_utilities.getRawFields(source_key);

    // Throw error if raw fields array is empty or doesn't exist
    if (!raw_fields || raw_fields.length === 0) {
        throw new Error(`No fields defined for source: ${source_key}`);
    }

    // Build delete statement
    const delete_statement = functions_utilities.buildDeleteStatement('bronze', source_key);

    // Build select statement
    const select_statement = `
    SELECT
        ${raw_fields.join(',\n        ')}
    FROM ${source_data_set}.${source_table};
    `;

    // Return statements
    return {
        delete_statement,
        select_statement
    };

}

// Export necessary function(s)
module.exports = {
    buildDesertBronze
}
