// Import schemas.js module exports
const schemas = require('includes/schemas');

// Extract schema map object from schemas.js module exports
const {
    schemaMap
} = schemas;

// Set meta data fields
const fieldSource = schemaMap.metaData.fields.source;
const fieldTimestamp = schemaMap.metaData.fields.timestamp;

function createDeleteStatement(
    dataSetSource,
    tableSource,
    dataSetDestination,
    tableDestination,
    key
) {
    return `
        DELETE FROM ${dataSetDestination}.${tableDestination}
        WHERE ${key} IN (
            SELECT DISTINCT
                ${key}
            FROM ${dataSetSource}.${tableSource}
        )
    `;
}

// Bronze
function desertBronze(sourceKey) {

    // Set data sets
    const dataSetSource = schemaMap.dataSets.staging;
    const dataSetDestination = schemaMap.dataSets.bronze;

    // Set tables
    const tableSource = schemaMap.tables.staging[sourceKey];
    const tableDestination = schemaMap.tables.bronze[sourceKey];

    // Set key field
    const key = `${sourceKey}_id`;

    // Build raw dimensions list
    const rawDimensions = schemaMap.fields.dimensions[sourceKey]
        .map(dimension => dimension.raw)
        .join(',\n            ');

    // Set meta data fields
    const fieldSource = schemaMap.metaData.fields.source;
    const fieldTimestamp = schemaMap.metaData.fields.timestamp;

    // Set meta data values
    const valueSource = schemaMap.metaData[sourceKey].source;
    const valueTimestamp = schemaMap.metaData[sourceKey].timestamp;

    // Build delete statement
    const deleteStatement = createDeleteStatement(
        dataSetSource,
        tableSource,
        dataSetDestination,
        tableDestination,
        key
    );


    const selectStatement = `
        SELECT
            ${rawDimensions},
            '${valueSource}' AS ${fieldSource},
            '${valueTimestamp}' AS ${fieldTimestamp},
        FROM ${dataSetSource}.${tableSource};
    `

    return {
        deleteStatement,
        selectStatement
    };

}

// Silver

// Build renaming CTE
function buildRenamingCte(sourceKey) {

    // Set source data set
    const dataSetSource = schemaMap.dataSets.bronze;

    // Set source table
    const tableSource = schemaMap.tables.bronze[sourceKey];

    // Set fields
    const fields = schemaMap.fields.dimensions[sourceKey];

    // Build rows where field is renamed to alias
    const rows = fields
        .map(field => `${field.raw} AS ${field.alias}`)
        .join(',\n                ');

    // Build final CTE
    const cte = `
        renaming_${sourceKey} AS (
            SELECT
                ${rows},
                ${fieldSource},
                ${fieldTimestamp}
            FROM ${dataSetSource}.${tableSource}
        )
    `;

    return cte;

}

function buildCastingCte(sourceKey) {

    // Set fields array
    const fields = schemaMap.fields.dimensions[sourceKey]

    // Build rows where field is renamed to alias
    const rows = fields
        .map(field => `CAST(${field.alias} AS ${field.type}) AS ${field.alias}`)
        .join(',\n                ');

    // Build final CTE
    const cte = `
        casting_${sourceKey} AS (
            SELECT
                ${rows}
            FROM renaming_${sourceKey}
        )
    `

    return cte;
}

function desertSilver(sourceKey) {

    // Set data sets
    const dataSetSource = schemaMap.dataSets.bronze;
    const dataSetDestination = schemaMap.dataSets.silver;

    // Set tables
    const tableSource = schemaMap.tables.bronze[sourceKey];
    const tableDestination = schemaMap.tables.silver[sourceKey];

    // Set key field
    const key = `${[sourceKey]}_id`;

    // Set delete statement
    const deleteStatement = createDeleteStatement(
        dataSetSource,
        tableSource,
        dataSetDestination,
        tableDestination,
        key
    );

    // Set select statement
    const selectStatement = `
        WITH
        ${buildRenamingCte(sourceKey)},
        ${buildCastingCte(sourceKey)}

        SELECT
            *
        FROM casting_${sourceKey};
    `

    return {
        deleteStatement,
        selectStatement
    };
}

// Gold

function desertSystemAlerts() {

    // Set data sets
    const dataSetSource = schemaMap.dataSets.silver;
    const dataSetDestination = schemaMap.dataSets.gold;

    // Set tables
    const tableSourceAlerts = schemaMap.tables.silver.alerts;
    const tableSourceRoutes = schemaMap.tables.silver.routes;
    const tableDestination = schemaMap.tables.gold.alerts;
    const keyAlerts = schemaMap.fields.keys.alerts;
    const dimensionsAlerts = schemaMap.fields.dimensions.alerts;
    const dimensionsRoutes = schemaMap.fields.dimensions.routes;

    const deleteStatement = createDeleteStatement(
        dataSetSource,
        tableSourceAlerts,
        dataSetDestination,
        tableDestination,
        keyAlerts
    );

    const selectStatement = `

        
        SELECT
            ${schemaMap.fields.dimensions.alerts
                .map(dim => `alerts.${dim.alias}`)
                .join(',\n            ')
            },
            ${schemaMap.fields.dimensions.routes
                .map(dim => `routes.${dim.alias}`)
                .join(',\n            ')
            },
            'ingestion_py_scripts' AS ${fieldSource},
            CURRENT_TIMESTAMP() AS ${fieldTimestamp}
        FROM ${dataSetSource}.${tableSourceAlerts} AS alerts
        LEFT JOIN ${dataSetSource}.${tableSourceRoutes} AS routes
            ON alerts.alert_route = routes.route_id;
    `;

    return {
        deleteStatement,
        selectStatement
    };
}

module.exports = {
    desertBronze,
    desertSilver,
    desertSystemAlerts
};
