// global variables
const schemas = require('includes/schemas');
const schemaMap = schemas.schemaMap;
const dataSet = schemaMap.dataSet;
const ingestionSource = schemaMap.fields.ingestion.source;
const ingestionTimestamp = schemaMap.fields.ingestion.timestamp;

function castDataTypes(fields) {
    return fields.map(field => {
        const [key, type] = Object.entries(field)[0];
        return `CAST(${key} AS ${type}) AS ${key}`
    })
}

function prependAppendString(
    targetString,
    stringToPrepend,
    stringToAppend,
) {
    return `${stringToPrepend}${targetString}${stringToAppend}`
}

function createDeleteStatement(
    sourceTable,
    destinationTable,
    key
) {
    return `
        DELETE FROM ${dataSet}.${destinationTable}
        WHERE
            ${key} IN (
                SELECT DISTINCT
                    ${key}
                FROM ${dataSet}.${sourceTable}
            )
        ;
    `
}

function createSelectStatement(
    sourceTable,
    dimensions
) {
    return `
        SELECT
            ${dimensions}
        FROM ${dataSet}.${sourceTable}
    `
}

function createJoinStatement(
    leftSource,
    rightSource,
    leftKey,
    rightKey
) {

    const leftDimensions = schemaMap.fields[leftSource].dimensions.map(dimension => Object.keys(dimension)[0]);
    const rightDimensions = schemaMap.fields[rightSource].dimensions.map(dimension => Object.keys(dimension)[0]);
    const leftDimensionsWithPrefix = leftDimensions.map(dimension => `${leftSource}.${dimension}`);
    const rightDimensionsWithPrefix = rightDimensions.map(dimension => `${rightSource}.${dimension}`);

    return `
        SELECT
            ${leftDimensionsWithPrefix},
            ${rightDimensionsWithPrefix}
        FROM ${leftSource}
        LEFT JOIN ${rightSource}
            ON ${leftSource}.${leftKey} = ${rightSource}.${rightKey}
    `
}
////////////////////////////////////////////////////////////////////////////////////////////////////////////////
function desertBronze(dataSource) {
    const sourceTable = schemaMap.tables.external[dataSource];
    const destinationTable = schemaMap.tables.bronze[dataSource];
    const key = schemaMap.fields[dataSource].key;
    const dimensions = schemaMap.fields[dataSource].dimensions.map(dimension => Object.keys(dimension)[0]);

    const deleteStatement = createDeleteStatement(
        sourceTable,
        destinationTable,
        key
    );

    const selectStatement = prependAppendString(
        createSelectStatement(
            sourceTable,
            dimensions
        ),
        '',
        ';'
    );

    return {
        deleteStatement,
        selectStatement
    }
}

function desertS1() {
    const sourceTableAlerts = schemaMap.tables.bronze.alerts;
    const sourceTableRoutes = schemaMap.tables.bronze.routes;
    const destinationTable = schemaMap.tables.silver.s1;
    const keyAlerts = schemaMap.fields.alerts.key;
    const keyRoutes = schemaMap.fields.routes.key;
    const dataTypesDimensionsAlerts = schemaMap.fields.alerts.dimensions
    const dataTypesDimensionsRoutes = schemaMap.fields.routes.dimensions;
    const dimensionsAlerts = schemaMap.fields.alerts.dimensions.map(dimension => Object.keys(dimension)[0]);
    const dimensionsRoutes = schemaMap.fields.routes.dimensions.map(dimension => Object.keys(dimension)[0]);

    const deleteStatement = createDeleteStatement(
        sourceTableAlerts,
        destinationTable,
        keyAlerts
    );

    const selectStatement = `
        WITH

        alerts AS (
            ${createSelectStatement(
                sourceTableAlerts,
                castDataTypes(dataTypesDimensionsAlerts)
            )}
        ),

        routes AS (
            ${createSelectStatement(
                sourceTableRoutes,
                castDataTypes(dataTypesDimensionsRoutes)
            )}
        )

        ${createJoinStatement(
            'alerts',
            'routes',
            keyAlerts,
            keyRoutes,
            'bronze'
        )}
        ;
    `

    return {
        deleteStatement,
        selectStatement
    }
}

function desertGold() {
    const sourceTable = schemaMap.tables.silver.s1;
    const destinationTable = schemaMap.tables.gold;
    const key = schemaMap.fields.alerts.key;
    const dimensionsAlerts = schemaMap.fields.alerts.dimensions.map(dimension => Object.keys(dimension)[0]);
    const dimensionsRoutes = schemaMap.fields.routes.dimensions.map(dimension => Object.keys(dimension)[0]);
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
    }
}

module.exports = {
    desertBronze,
    desertS1,
    desertGold
}
