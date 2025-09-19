// Import schemas
const {
    schema
} = require('includes/schemas');

// Get metadata fields
const ingestionSource = schema.metadata.source;
const ingestionTimestamp = schema.metadata.timestamp;

// Build CTE for renaming and casting fields
function buildCteStandarized(sourceKey) {
    // Get source data set
    const sourceDataSet = schema.dataSets.bronze;
    // Get source table
    const sourceTable = schema.tables.bronze[sourceKey];
    // Get dimension array for sourceKey
    const dimensionArray = schema.sources[sourceKey].dimensions;
    // Get metric array for sourceKey
    const metricArray = schema.sources[sourceKey].metrics || [];
    // Combine dimension and metric arrays into single array
    const fieldArray = [
        ...dimensionArray,
        ...metricArray
    ];
    // Build rows where fields get casted and renamed
    const rows = fieldArray.map(
        field => `CAST(${field.raw} AS ${field.type}) AS ${field.alias}`
    );
    // Return renaming & casting CTE
    return `
    standardized_${sourceKey} AS (
        SELECT
            ${rows.join(',\n            ')}
        FROM ${sourceDataSet}.${sourceTable}
    )`;
}

// Build CTE for grouped fields
function buildCteGrouped(sourceKey) {
    // Get dimension and metric arrays for sourceKey
    const dimensionArray = schema.sources[sourceKey].dimensions || [];
    const metricArray = schema.sources[sourceKey].metrics || [];
    // Build array of dimension aliases
    const dimAliases = dimensionArray
        .map(f => f.alias);
    // Build array of aggregated metric aliases
    const metAliases = metricArray.map(f => `SUM(${f.alias}) AS ${f.alias}`);
    // Combine dimension and metric alias arrays into single array
    const fields = [
        ...dimAliases,
        ...metAliases
    ];
    // Return grouped CTE
    return `
    grouped_${sourceKey} AS (
        SELECT
            ${fields.join(',\n            ')}
        FROM standardized_${sourceKey}
        GROUP BY
            ${dimAliases.join(',\n            ')}
    )
    `;
}

// Build desert statement for silver layer
function buildDesertSilver(sourceKey) {
    const deleteStatement = `${functions_utilities.buildDeleteStatement('silver', sourceKey)}`;

    const selectStatement = `
    WITH
    ${buildCteStandarized(sourceKey)},
    ${buildCteGrouped(sourceKey)}
    SELECT
        *
    FROM grouped_${sourceKey};`;

    return {
        deleteStatement,
        selectStatement
    };
}
module.exports = {
    buildDesertSilver
};
