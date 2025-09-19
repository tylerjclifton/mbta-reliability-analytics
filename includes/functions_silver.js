const {
    schema
} = require('includes/schema');
const functions_utilities = require('./functions_utilities'); // adjust path

// Build standardized CTE (renaming + casting)
function buildCteStandardized(source_array) {
    const source_data_set = schema.data_sets.bronze;
    const source_table = schema.tables.bronze[source_array];
    const fields_array = schema.fields[source_array];

    if (!fields_array || fields_array.length === 0) {
        throw new Error(`No fields defined for source_array: ${source_array}`);
    }

    const rows = fields_array.map(
        f => `CAST(${f.raw} AS ${f.type}) AS ${f.alias}`
    );

    return `
    standardized_${source_array} AS (
        SELECT
            ${rows.join(',\n            ')}
        FROM ${source_data_set}.${source_table}
    )`;
}

// Build mapping CTE dynamically using schema.taxonomy
function buildCteMapping(source_array) {
    const fields_array = schema.fields[source_array];
    const mapped_rows = fields_array.map(f => {
        // Check if taxonomy exists for this source & field
        if (schema.taxonomy[source_array] && schema.taxonomy[source_array][f.alias]) {
            const mapping = schema.taxonomy[source_array][f.alias];
            const cases = Object.entries(mapping)
                .map(([val, label]) => `WHEN '${val}' THEN '${label}'`)
                .join('\n                ');
            return `CASE ${f.alias}
                ${cases}
                ELSE 'UNKNOWN'
            END AS ${f.alias}`;
        }
        // Default: just pass-through alias
        return f.alias;
    });

    return `
    mapped_${source_array} AS (
        SELECT
            ${mapped_rows.join(',\n            ')}
        FROM standardized_${source_array}
    )`;
}

// Build silver desert
function buildDesertSilver(source_array) {
    const delete_statement = functions_utilities.buildDeleteStatement('silver', source_array);

    const select_statement = `
    WITH
    ${buildCteStandardized(source_array)},
    ${buildCteMapping(source_array)}
    SELECT
        *
    FROM mapped_${source_array};
    `;

    return {
        delete_statement,
        select_statement
    };
}

module.exports = {
    buildDesertSilver
};
