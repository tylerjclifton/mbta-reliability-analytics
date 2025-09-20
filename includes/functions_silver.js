// Import schema
const {
    schema
} = require('includes/schema');

// Build standardized CTE (renaming + casting)
function buildCteStandardized(source_key) {

    // Get source data set and table
    const source_data_set = schema.data_sets.bronze;
    const source_table = schema.tables.bronze[source_key];

    // Get source's fields array
    const fields_array = schema.fields[source_key];

    // Throw error if fields array is empty or doesn't exist
    if (!fields_array || fields_array.length === 0) {
        throw new Error(`No fields defined for source: ${source_key}`);
    }

    // Build rows for renaming and casting each item in fields array
    const rows = fields_array.map(
        field => `CAST(${field.raw} AS ${field.type}) AS ${field.alias}`
    );

    // Return standardized CTE
    return `
    standardized_${source_key} AS (
        SELECT
            ${rows.join(',\n            ')}
        FROM ${source_data_set}.${source_table}
    )`;

}

// Build mapping CTE (applying taxonomy)
function buildCteMapping(source_key) {

    // Get source's fields array
    const fields_array = schema.fields[source_key];

    // Iterate through fields array and apply taxonomy rules where available
    const mapped_rows = fields_array.map(f => {

        // Check if taxonomy exists for this source and field alias
        if (schema.taxonomy[source_key] && schema.taxonomy[source_key][f.alias]) {

            // Retrieve the taxonomy mapping for this field
            const mapping = schema.taxonomy[source_key][f.alias];

            // Build CASE WHEN statements from mapping (val → label)
            const cases = Object.entries(mapping)
                .map(([val, label]) => `WHEN '${val}' THEN '${label}'`)
                .join('\n                ');

            // Return CASE expression applying taxonomy mapping,
            // defaulting to 'UNKNOWN' if no match is found
            return `CASE ${f.alias}
                ${cases}
                ELSE 'UNKNOWN'
            END AS ${f.alias}`;
        }

        // If no taxonomy mapping exists, just return the field alias
        return f.alias;

    });


    // Return mapped CTE
    return `
    mapped_${source_key} AS (
        SELECT
            ${mapped_rows.join(',\n            ')}
        FROM standardized_${source_key}
    )`;

}

// Build desert statement for silver layer
function buildDesertSilver(source_key) {

    // Build delete statement
    const delete_statement = functions_utilities.buildDeleteStatement('silver', source_key);

    // Build select statement
    const select_statement = `
    WITH
    ${buildCteStandardized(source_key)},
    ${buildCteMapping(source_key)}
    SELECT
        *
    FROM mapped_${source_key};
    `;

    // Return statements
    return {
        delete_statement,
        select_statement
    };
}

// Export necessary function(s)
module.exports = {
    buildDesertSilver
};
