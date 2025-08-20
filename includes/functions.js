const schemas = require('includes/schemas');
const {
    schemaMap
} = schemas;
const ingestionSource = schemaMap.fields.ingestion.source;
const ingestionTimestamp = schemaMap.fields.ingestion.timestamp;

function renameFields(fieldsArray) {
    return fieldsArray.map(field => { // Use the parameter name
        return `${field.raw} AS ${field.alias}`;
    });
}

function castFields(fieldsArray) {
    return fieldsArray.map(field => { // Use the parameter name
        return `CAST(${field.alias} AS ${field.type}) AS ${field.alias}`;
    });
}

function wrapString(
    targetString,
    stringToPrepend,
    stringToAppend,
) {
    return `${stringToPrepend}${targetString}${stringToAppend}`;
}

function createDeleteStatement(
    dataSetSource,
    tableSource,
    destinationDataSet,
    tableDestination,
    key
) {
    return `
        DELETE FROM ${destinationDataSet}.${tableDestination}
        WHERE ${key} IN (
            SELECT DISTINCT
                ${key}
            FROM ${dataSetSource}.${tableSource}
        )
    `;
}

function createSelectStatement(
    dataSetSource,
    tableSource,
    dimensions
) {

    const dimensionList = Array.isArray(dimensions) ? dimensions.join(',\n            ') : dimensions;
    return `
        SELECT
            ${dimensionList}
        FROM ${dataSetSource}.${tableSource}
    `;

}

function getFinalFieldsArray() {
    const finalFields = [];

    // Get all dimension objects (alerts, routes, etc.)
    const dimensions = schemaMap.fields.dimensions;

    // Iterate through each object in dimensions
    Object.keys(dimensions).forEach(objectKey => {
        const objectDimensions = dimensions[objectKey];

        // Extract alias values from each dimension
        objectDimensions.forEach(dimension => {
            if (dimension.alias) {
                finalFields.push(dimension.alias);
            }
        });
    });

    return finalFields;
}

function desertBronze(dataSource) {

    const dataSetSource = schemaMap.dataSets.staging;
    const tableSource = schemaMap.tables.staging[dataSource];
    const destinationDataSet = schemaMap.dataSets.bronze;
    const tableDestination = schemaMap.tables.bronze[dataSource];
    const key = schemaMap.fields.keys[dataSource];
    const rawDimensions = schemaMap.fields.dimensions[dataSource].map(dimension => dimension.raw);

    const deleteStatement = createDeleteStatement(
        dataSetSource,
        tableSource,
        destinationDataSet,
        tableDestination,
        key
    );

    const selectStatement = wrapString(
        createSelectStatement(
            dataSetSource,
            tableSource,
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
    const dataSetSource = schemaMap.dataSets.bronze;
    const tableSourceAlerts = schemaMap.tables.bronze.alerts;
    const tableSourceRoutes = schemaMap.tables.bronze.routes;
    const destinationDataSet = schemaMap.dataSets.silver;
    const tableDestination = schemaMap.tables.silver.alerts; // Fixed: should be silver table
    const keyAlerts = schemaMap.fields.keys.alerts; // Fixed: correct path to keys
    const dimensionsAlerts = schemaMap.fields.dimensions.alerts; // Fixed: correct path
    const dimensionsRoutes = schemaMap.fields.dimensions.routes; // Fixed: correct path
    const ingestionSource = schemaMap.fields.ingestion.source; // Define ingestion fields
    const ingestionTimestamp = schemaMap.fields.ingestion.timestamp;

    const deleteStatement = createDeleteStatement(
        dataSetSource,
        tableSourceAlerts,
        destinationDataSet,
        tableDestination,
        keyAlerts
    );

    const selectStatement = `
        WITH
            renaming_alerts AS (
                ${createSelectStatement(
                    dataSetSource,
                    tableSourceAlerts,
                    renameFields(dimensionsAlerts)
                )}
            ),
            renaming_routes AS (
                ${createSelectStatement(
                    dataSetSource,
                    tableSourceRoutes,
                    renameFields(dimensionsRoutes)
                )}
            ),
            casting_alerts AS (
                ${createSelectStatement(
                    dataSetSource,
                    tableSourceAlerts,
                    castFields(dimensionsAlerts)
                )}
            ),
            casting_routes AS (
                ${createSelectStatement(
                    dataSetSource,
                    tableSourceAlerts,
                    castFields(dimensionsRoutes)
                )}
            )
        
        SELECT
        ${schemaMap.fields.dimensions.alerts.map(dim => `    alerts.${dim.alias}`).join(',\n')},
        ${schemaMap.fields.dimensions.routes.map(dim => `    routes.${dim.alias}`).join(',\n')},
            'ingestion_py_scripts' AS ${ingestionSource},
            CURRENT_TIMESTAMP() AS ${ingestionTimestamp}
        FROM alerts
        LEFT JOIN routes
            ON alerts.alert_route = routes.route_id;
    `;

    return {
        deleteStatement,
        selectStatement
    };
}

function desertGold() {
    const dataSetSource = schemaMap.dataSets.silver;
    const dataSetDestination = schemaMap.dataSets.gold;
    const tableSource = schemaMap.tables.silver.alerts;
    const tableDestination = schemaMap.tables.gold.alerts;
    const keyAlerts = schemaMap.fields.keys.alerts;
    const dimensionsAlerts = schemaMap.fields.dimensions.alerts.map(dimension => dimension.alias);
    const dimensionsRoutes = schemaMap.fields.dimensions.routes.map(dimension => dimension.alias);
    const fields = dimensionsAlerts.concat(dimensionsRoutes);

    const deleteStatement = createDeleteStatement(
        dataSetSource,
        tableSource,
        dataSetDestination,
        tableDestination,
        keyAlerts
    );

    const selectStatement = wrapString(
        createSelectStatement(
            dataSetSource,
            tableSource,
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
