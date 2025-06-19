function createSelectStatement(
    dataSet,
    sourceTable,
    dimensions,
    ingestionInfo
) {
    return `
    SELECT
        ${dimensions},
        ${ingestionInfo}
    FROM ${dataSet + '.' + sourceTable}
    GROUP BY ALL;`
}

function createDeleteStatement(
    dataSet,
    sourceTable,
    destinationTable,
    key
) {
    return `
    DELETE FROM ${dataSet + '.' + destinationTable}
    WHERE
        ${key} IN (
            SELECT DISTINCT
                ${key}
            FROM ${dataSet + '.' + sourceTable}
        );`
}

function desert(
    dataSet,
    sourceTable,
    destinationTable,
    key,
    dimensions,
    ingestionInfo
) {

    const deleteStatement = createDeleteStatement(
        dataSet,
        sourceTable,
        destinationTable,
        key
    )

    const selectStatement = createSelectStatement(
        dataSet,
        sourceTable,
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
