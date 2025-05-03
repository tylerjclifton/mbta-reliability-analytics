// variable imports
const schemas = require('./schemas');

// data sets
const data_set = schemas.data_set;

// tables
const alerts_tables_external = schemas.alerts.tables.external;
const alerts_tables_bronze = schemas.alerts.tables.bronze;
const alerts_tables_s1 = schemas.alerts.tables.s1;
const alerts_tables_gold = schemas.alerts.tables.gold;

// keys
const alerts_keys = schemas.alerts.fields.keys;

// dates
const alerts_dates = schemas.alerts.fields.dates;

// dimensions
const alerts_dimensions_bronze = schemas.alerts.fields.dimensions.bronze;
const etl_fields = schemas.alerts.fields.etl_fields;

function SelectStatement(
    source_table,
    dates,
    dimensions,
    etl_fields
) {
    return `
    SELECT
        ${dates},
        ${dimensions},
        ${etl_fields}
    FROM ${data_set + source_table}
    GROUP BY ALL`
}

function DeleteStatement(
    destination_table,
    source_table,
    key_field
) {
    return `
    DELETE FROM ${data_set + destination_table}
    WHERE
        ${key_field} IN (
            SELECT DISTINCT
                ${key_field}
            FROM ${data_set + source_table}
        )`
}

function BronzeDesert() {

    const delete_statement = DeleteStatement(
        alerts_tables_bronze,
        alerts_tables_external,
        alerts_keys
    )

    const select_statement = SelectStatement(
        alerts_tables_external,
        alerts_dates,
        alerts_dimensions_bronze,
        etl_fields
    )

    return {
        delete_statement,
        select_statement
    }
}

module.exports = {
    BronzeDesert
}
