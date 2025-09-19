// Import schemas
const {
    schema
} = require('includes/schema');

// Build desert statement for bronze layer
function buildDesertBronze(sourceKey) {

    // Get source data set
    const sourceDataSet = schema.data_sets.staging;

    // Get source table
    const sourceTable = schema.tables.staging[sourceKey];

    // Get raw values from dimensions and metrics arrays
    const {
        rawDimensions,
        rawMetrics
    } = functions_utilities.getRawFields(sourceKey);

    // Combine raw dimensions and metrics arrays into single array
    const rawFields = [
        ...rawDimensions,
        ...rawMetrics
    ];

    // Build delete statement
    const deleteStatement = functions_utilities.buildDeleteStatement('bronze', sourceKey);

    // Build select statement
    const selectStatement = `
    SELECT
        ${rawFields.join(',\n        ')}
    FROM ${sourceDataSet}.${sourceTable};
    `;

    // Return statements
    return {
        deleteStatement,
        selectStatement
    };

}

module.exports = {
    buildDesertBronze
}
