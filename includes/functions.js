const schemas = require('includes/schemas');
const schemaMap = schemas.schemaMap;
const dataSet = schemaMap.dataSet;
const ingestionSource = schemaMap.fields.ingestion.source;
const ingestionTimestamp = schemaMap.fields.ingestion.timestamp;

function renameCastDataTypes(fields) {
    return fields.map(field => {
        return `CAST(${field.rawName} AS ${field.dataType}) AS ${field.newName}`;
    });
}

function prependAppendString(
    targetString,
    stringToPrepend,
    stringToAppend,
) {
    return `${stringToPrepend}${targetString}${stringToAppend}`;
}

function createDeleteStatement(
    sourceTable,
    destinationTable,
    key
) {
    return `
        DELETE FROM ${dataSet}.${destinationTable}
        WHERE ${key} IN (
            SELECT DISTINCT ${key}
            FROM ${dataSet}.${sourceTable}
        )
    `;
}

function createSelectStatement(
    sourceTable,
    dimensions
) {
    const dimensionList = Array.isArray(dimensions) ? dimensions.join(',\n            ') : dimensions;
    return `
        SELECT
            ${dimensionList}
        FROM ${dataSet}.${sourceTable}
    `;
}

// BRONZE LEVEL - Simple copy with ingestion metadata only
function desertBronze(dataSource) {
    const sourceTable = schemaMap.tables.external[dataSource];
    const destinationTable = schemaMap.tables.bronze[dataSource];
    const key = schemaMap.fields[dataSource].dimensions.find(dim => dim.rawName === schemaMap.fields[dataSource].key).rawName;
    const rawDimensions = schemaMap.fields[dataSource].dimensions.map(dimension => dimension.rawName);

    const deleteStatement = createDeleteStatement(
        sourceTable,
        destinationTable,
        key
    );

    const selectStatement = prependAppendString(
        createSelectStatement(
            sourceTable,
            rawDimensions
        ),
        '',
        ';'
    );

    return {
        deleteStatement,
        selectStatement
    };
}

// S1 LEVEL - Renaming, casting, denormalizing
function desertS1() {
    const sourceTableAlerts = schemaMap.tables.bronze.alerts;
    const sourceTableRoutes = schemaMap.tables.bronze.routes;
    const destinationTable = schemaMap.tables.silver.s1;
    const keyAlerts = schemaMap.fields.alerts.key;
    const dataTypesDimensionsAlerts = schemaMap.fields.alerts.dimensions;
    const dataTypesDimensionsRoutes = schemaMap.fields.routes.dimensions;

    const deleteStatement = createDeleteStatement(
        sourceTableAlerts,
        destinationTable,
        keyAlerts
    );

    // Cast and rename fields at S1 level
    const alertsWithCasting = renameCastDataTypes(dataTypesDimensionsAlerts);
    const routesWithCasting = renameCastDataTypes(dataTypesDimensionsRoutes);

    const selectStatement = `
        WITH
        alerts AS (
            ${createSelectStatement(sourceTableAlerts, alertsWithCasting)}
        ),
        routes AS (
            ${createSelectStatement(sourceTableRoutes, routesWithCasting)}
        )
        SELECT
            ${schemaMap.fields.alerts.dimensions.map(dim => `alerts.${dim.newName}`).join(',\n            ')},
            ${schemaMap.fields.routes.dimensions.map(dim => `routes.${dim.newName}`).join(',\n            ')},
            'ingestion_py_scripts' AS ${ingestionSource},
            CURRENT_TIMESTAMP() AS ${ingestionTimestamp}
        FROM alerts
        LEFT JOIN routes
            ON alerts.route = routes.route_id
        ;
    `;

    return {
        deleteStatement,
        selectStatement
    };
}

function desertGold() {
    const sourceTable = schemaMap.tables.silver.s1;
    const destinationTable = schemaMap.tables.gold.route_alerts;
    const key = schemaMap.fields.alerts.key;
    const dimensionsAlerts = schemaMap.fields.alerts.dimensions.map(dimension => dimension.newName);
    const dimensionsRoutes = schemaMap.fields.routes.dimensions.map(dimension => dimension.newName);
    const fields = dimensionsAlerts.concat(dimensionsRoutes);

    const deleteStatement = createDeleteStatement(
        sourceTable,
        destinationTable,
        key
    );

    const selectStatement = prependAppendString(
        createSelectStatement(
            sourceTable,
            fields
        ),
        '',
        ';'
    );

    return {
        deleteStatement,
        selectStatement
    };
}

module.exports = {
    desertBronze,
    desertS1,
    desertGold
};
