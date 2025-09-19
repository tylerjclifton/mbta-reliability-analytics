const {
    schema
} = require('includes/schema');
const functions_utilities = require('./functions_utilities'); // adjust path

// Build standardized CTE (renaming + casting)
function buildCteStandardized(sourceKey) {
    const sourceDataSet = schema.data_sets.bronze;
    const sourceTable = schema.tables.bronze[sourceKey];
    const fieldsArray = schema.fields[sourceKey];

    if (!fieldsArray || fieldsArray.length === 0) {
        throw new Error(`No fields defined for sourceKey: ${sourceKey}`);
    }

    const rows = fieldsArray.map(
        f => `CAST(${f.raw} AS ${f.type}) AS ${f.alias}`
    );

    return `
    standardized_${sourceKey} AS (
        SELECT
            ${rows.join(',\n            ')}
        FROM ${sourceDataSet}.${sourceTable}
    )`;
}

// Build mapping CTE dynamically using schema.taxonomy
function buildCteMapping(sourceKey) {
    const fieldsArray = schema.fields[sourceKey];
    const mappedRows = fieldsArray.map(f => {
        // Check if taxonomy exists for this source & field
        if (schema.taxonomy[sourceKey] && schema.taxonomy[sourceKey][f.alias]) {
            const mapping = schema.taxonomy[sourceKey][f.alias];
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
    mapped_${sourceKey} AS (
        SELECT
            ${mappedRows.join(',\n            ')}
        FROM standardized_${sourceKey}
    )`;
}

// Build silver desert
function buildDesertSilver(sourceKey) {
    const delete_statement = functions_utilities.buildDeleteStatement('silver', sourceKey);

    const select_statement = `
    WITH
    ${buildCteStandardized(sourceKey)},
    ${buildCteMapping(sourceKey)}
    SELECT
        *
    FROM mapped_${sourceKey};
    `;

    return {
        delete_statement,
        select_statement
    };
}

module.exports = {
    buildDesertSilver
};
