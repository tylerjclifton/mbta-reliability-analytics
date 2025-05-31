// import variables
const schemas = require('./schemas');

// data set
const dataSet = schemas.alerts.dataSet;

// ingestion info
const ingestionInfo = schemas.alerts.fields.ingestionInfo;


function createSelectStatement(
    sourceTable,
    dates,
    dimensions,
    ingestionInfo
) {
    return `
    SELECT
        ${dates},
        ${dimensions},
        ${ingestionInfo}
    FROM ${dataSet + sourceTable}
    GROUP BY ALL;`
}

function createDeleteStatement(
    sourceTable,
    destinationTable,
    key
) {
    return `
    DELETE FROM ${dataSet + destinationTable}
    WHERE
        ${key} IN (
            SELECT DISTINCT
                ${key}
            FROM ${dataSet + sourceTable}
        );`
}

function desert(sourceTable, destinationTable, key, dates, dimensions) {

    const deleteStatement = createDeleteStatement(
        sourceTable,
        destinationTable,
        key
    )

    const selectStatement = createSelectStatement(
        sourceTable,
        dates,
        dimensions,
        ingestionInfo
    )

    return {
        deleteStatement,
        selectStatement
    }
}

module.exports = {
    desert
}
