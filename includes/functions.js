/**
 * Data pipeline functions for MBTA alerts and routes processing
 * Handles transformations across bronze, silver, and gold layers
 */

// Import schemas.js module exports
const schemas = require('includes/schemas');

// Extract schema map object from schemas.js module exports
const {
    schemaMap
} = schemas;

// Set meta data field names from schema
const fieldSource = schemaMap.metaData.fields.source; // 'ingestion_source'
const fieldTimestamp = schemaMap.metaData.fields.timestamp; // 'ingestion_timestamp'

/**
 * Creates a DELETE statement for incremental data loading
 * Removes existing records that will be replaced with new data
 * 
 * @param {string} dataSetSource - Source dataset name
 * @param {string} tableSource - Source table name  
 * @param {string} dataSetDestination - Destination dataset name
 * @param {string} tableDestination - Destination table name
 * @param {string} key - Primary key field for matching records
 * @returns {string} SQL DELETE statement
 */
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

/**
 * BRONZE LAYER TRANSFORMATION
 * Copies raw data from staging to bronze with minimal transformation
 * Adds ingestion metadata fields for data lineage tracking
 * 
 * @param {string} sourceKey - Data source identifier ('alerts' or 'routes')
 * @returns {object} Object containing deleteStatement and selectStatement
 */
function desertBronze(sourceKey) {

    // Set source and destination datasets (staging → bronze)
    const dataSetSource = schemaMap.dataSets.staging;
    const dataSetDestination = schemaMap.dataSets.bronze;

    // Set source and destination table names
    const tableSource = schemaMap.tables.staging[sourceKey];
    const tableDestination = schemaMap.tables.bronze[sourceKey];

    // Set primary key field for incremental loading
    const key = schemaMap.fields.keys[sourceKey]; // Fixed: use schema key instead of template literal

    // Build comma-separated list of raw field names from schema
    const rawDimensions = schemaMap.fields.dimensions[sourceKey]
        .map(dimension => dimension.raw)
        .join(',\n            ');

    // Get metadata values specific to this source type
    const valueSource = schemaMap.metaData[sourceKey].source; // 'ingestion_py_scripts'
    const valueTimestamp = schemaMap.metaData[sourceKey].timestamp; // 'CURRENT_TIMESTAMP()'

    // Build DELETE statement for incremental loading
    const deleteStatement = createDeleteStatement(
        dataSetSource,
        tableSource,
        dataSetDestination,
        tableDestination,
        key
    );

    // Build SELECT statement to copy raw data with metadata
    const selectStatement = `
        SELECT
            ${rawDimensions},
            '${valueSource}' AS ${fieldSource},
            ${valueTimestamp} AS ${fieldTimestamp}
        FROM ${dataSetSource}.${tableSource};
    `;

    return {
        deleteStatement,
        selectStatement
    };
}

/**
 * SILVER LAYER HELPER - Build renaming CTE
 * Creates a CTE that renames raw fields to their clean aliases
 * 
 * @param {string} sourceKey - Data source identifier ('alerts' or 'routes')
 * @returns {string} SQL CTE for field renaming
 */
function buildRenamingCte(sourceKey) {

    // Set bronze dataset and table as source for silver transformation
    const dataSetSource = schemaMap.dataSets.bronze;
    const tableSource = schemaMap.tables.bronze[sourceKey];

    // Get field mapping definitions from schema
    const fields = schemaMap.fields.dimensions[sourceKey];

    // Build field renaming expressions (raw_name AS clean_alias)
    const rows = fields
        .map(field => `${field.raw} AS ${field.alias}`)
        .join(',\n                ');

    // Build CTE with renamed fields plus metadata fields
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

/**
 * SILVER LAYER HELPER - Build casting CTE
 * Creates a CTE that casts fields to their proper data types
 * 
 * @param {string} sourceKey - Data source identifier ('alerts' or 'routes')
 * @returns {string} SQL CTE for type casting
 */
function buildCastingCte(sourceKey) {

    // Get field definitions with type information
    const fields = schemaMap.fields.dimensions[sourceKey];

    // Build type casting expressions (CAST(field AS TYPE) AS field)
    const rows = fields
        .map(field => `CAST(${field.alias} AS ${field.type}) AS ${field.alias}`)
        .join(',\n                ');

    // Build CTE that casts all fields to proper types
    const cte = `
        casting_${sourceKey} AS (
            SELECT
                ${rows},
                ${fieldSource},
                ${fieldTimestamp}
            FROM renaming_${sourceKey}
        )
    `; // Fixed: added missing metadata fields

    return cte;
}

/**
 * SILVER LAYER TRANSFORMATION
 * Transforms bronze data by renaming fields and casting to proper types
 * Creates clean, standardized data ready for business logic
 * 
 * @param {string} sourceKey - Data source identifier ('alerts' or 'routes')
 * @returns {object} Object containing deleteStatement and selectStatement
 */
function desertSilver(sourceKey) {

    // Set source and destination datasets (bronze → silver)
    const dataSetSource = schemaMap.dataSets.bronze;
    const dataSetDestination = schemaMap.dataSets.silver;

    // Set source and destination table names
    const tableSource = schemaMap.tables.bronze[sourceKey];
    const tableDestination = schemaMap.tables.silver[sourceKey];

    // Set primary key field for incremental loading
    const key = schemaMap.fields.keys[sourceKey]; // Fixed: use schema key

    // Build DELETE statement for incremental loading
    const deleteStatement = createDeleteStatement(
        dataSetSource,
        tableSource,
        dataSetDestination,
        tableDestination,
        key
    );

    // Build SELECT statement with renaming and casting CTEs
    const selectStatement = `
        WITH
        ${buildRenamingCte(sourceKey)},
        ${buildCastingCte(sourceKey)}

        SELECT
            *
        FROM casting_${sourceKey};
    `;

    return {
        deleteStatement,
        selectStatement
    };
}

/**
 * GOLD LAYER TRANSFORMATION - System Alerts
 * Creates business-ready data by joining alerts with route information
 * Produces enriched alerts table for analytics and reporting
 * 
 * @returns {object} Object containing deleteStatement and selectStatement
 */
function desertSystemAlerts() {

    // Set source and destination datasets (silver → gold)
    const dataSetSource = schemaMap.dataSets.silver;
    const dataSetDestination = schemaMap.dataSets.gold;

    // Set source tables (both alerts and routes from silver)
    const tableSourceAlerts = schemaMap.tables.silver.alerts;
    const tableSourceRoutes = schemaMap.tables.silver.routes;

    // Set destination table (joined alerts in gold)
    const tableDestination = schemaMap.tables.gold.alerts;

    // Set primary key for incremental loading (alerts table key)
    const keyAlerts = schemaMap.fields.keys.alerts;

    // Get dimension definitions for field selection
    const dimensionsAlerts = schemaMap.fields.dimensions.alerts;
    const dimensionsRoutes = schemaMap.fields.dimensions.routes;

    // Build DELETE statement for incremental loading
    const deleteStatement = createDeleteStatement(
        dataSetSource,
        tableSourceAlerts,
        dataSetDestination,
        tableDestination,
        keyAlerts
    );

    // Build SELECT statement with LEFT JOIN to enrich alerts with route data
    const selectStatement = `
        SELECT
            ${dimensionsAlerts
                .map(dim => `alerts.${dim.alias}`)
                .join(',\n            ')
            },
            ${dimensionsRoutes
                .map(dim => `routes.${dim.alias}`)
                .join(',\n            ')
            },
            alerts.${fieldSource},
            alerts.${fieldTimestamp}
        FROM ${dataSetSource}.${tableSourceAlerts} AS alerts
        LEFT JOIN ${dataSetSource}.${tableSourceRoutes} AS routes
            ON alerts.alert_route = routes.route_id;
    `; // Fixed: use schema metadata value instead of hardcoded string

    return {
        deleteStatement,
        selectStatement
    };
}

// Export all transformation functions
module.exports = {
    desertBronze,
    desertSilver,
    desertSystemAlerts
};
