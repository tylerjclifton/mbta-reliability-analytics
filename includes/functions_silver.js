// Import schema
const {
    schema
} = require('includes/schema');

// Build standardized CTE (renaming + casting)
function buildCteStandardized(source_key) {

    // Get source data set and table
    const source_data_set = schema.data_sets.bronze;
    const source_table = schema.tables.bronze[source_key];

    // Get source fields array
    const fields_array = schema.fields[source_key];

    // Throw error if fields array is empty or doesn't exist
    if (!fields_array || fields_array.length === 0) {
        throw new Error(`No fields defined for source: ${source_key}`);
    }

    // Build rows for renaming and casting each field in fields array
    const rows = fields_array.map(
        field => `CAST(${field.raw} AS ${field.type}) AS ${field.alias}`
    );

    // Return standardized CTE
    return `
    standardized_${source_key} AS (
        SELECT
            ${rows.join(',\n            ')}
        FROM ${source_data_set}.${source_table}
        GROUP BY ALL
    )`;

}

// Build mapping CTE (applying taxonomy)
function buildCteMapping(source_key) {

    // Get source fields array
    const fields_array = schema.fields[source_key];

    // Iterate through fields array and apply taxonomy rules where available
    const mapped_rows = fields_array.map(f => {

        // Check if taxonomy exists for this source and field alias
        if (schema.taxonomy[source_key] && schema.taxonomy[source_key][f.alias]) {

            // Retrieve the taxonomy mapping for this field
            const mapping = schema.taxonomy[source_key][f.alias];

            // Build CASE WHEN statements from mapping (val → label)
            const cases = Object.entries(mapping)
                .map(([val, label]) => `WHEN '${val}' THEN '${label}'`)
                .join('\n                ');

            // Return CASE expression applying taxonomy mapping,
            // defaulting to 'UNKNOWN' if no match is found
            return `CASE ${f.alias}
                ${cases}
                ELSE 'UNKNOWN'
            END AS ${f.alias}`;
        }

        // If no taxonomy mapping exists, just return the field alias
        return f.alias;

    });

    // Return mapped CTE
    return `
    mapped_${source_key} AS (
        SELECT
            ${mapped_rows.join(',\n            ')}
        FROM standardized_${source_key}
    )`;

}

// Build desert statement for silver layer
function buildDesertSilver(source_key) {

    // Build delete statement
    const delete_statement = functions_utilities.buildDeleteStatement('silver', source_key);

    // Initialize select statement variable
    let select_statement;

    // If source key is alerts
    if (source_key === 'alerts') {

        // Get stops data set and table
        const stops_data_set = schema.data_sets.silver;
        const stops_table = schema.tables.silver.stops;

        // Get alerts and stops field arrays
        const alerts_fields = schema.fields['alerts'];
        const stops_fields = schema.fields['stops'];

        // Get final alerts fields
        const final_alerts_fields = alerts_fields.map(field => `${field.alias}`)

        // Get fields for alerts with mapped stops join
        const final_alerts_with_join_prefix = alerts_fields
            .filter(field => field.alias !== 'stop_id') // exclude stop_id
            .map(field => `a.${field.alias}`);

        // Get stops id and name fields
        const stops_id_field = stops_fields.find(field => field.alias.toLowerCase().includes('_id')).alias;
        const stops_name_field = stops_fields.find(field => field.alias.toLowerCase().includes('_name')).alias;

        // Create select statement for alerts
        select_statement = `
    WITH
    ${buildCteStandardized(source_key)},

    stops_lookup AS (
        SELECT DISTINCT
            ${stops_id_field},
            ${stops_name_field}
        FROM ${stops_data_set}.${stops_table}
    ),

    alerts_with_valid_stops AS (
        SELECT
            *
        FROM standardized_${source_key}
        WHERE REGEXP_CONTAINS(stop_id, r'^[0-9]{5,6}$')
    ),

    alerts_with_mapped_stops AS (
        SELECT
            ${final_alerts_with_join_prefix.join(',\n            ')},
            COALESCE(s1.stop_id, s2.stop_id, 'Not Listed') AS stop_id
        FROM standardized_alerts a
        LEFT JOIN stops_lookup s1
            ON UPPER(a.alert_description) LIKE '%' || UPPER(s1.stop_name) || '%'
        LEFT JOIN stops_lookup s2
            ON UPPER(a.alert_header) LIKE '%' || UPPER(s2.stop_name) || '%'
        WHERE NOT REGEXP_CONTAINS(a.stop_id, r'^[0-9]{5,6}$')
    )

    SELECT
        *
    FROM alerts_with_valid_stops

    UNION ALL

    SELECT
        ${final_alerts_fields.join(',\n        ')}
    FROM alerts_with_mapped_stops;
        `;

    } else if (source_key in schema.taxonomy) {
        // Standard processing
        select_statement = `
    WITH
    ${buildCteStandardized(source_key)},
    ${buildCteMapping(source_key)}

    SELECT
        *
    FROM mapped_${source_key};
        `;
    } else {
        select_statement = `
    WITH
    ${buildCteStandardized(source_key)}

    SELECT
        *
    FROM standardized_${source_key};
    `
    }

    // Return statements
    return {
        delete_statement,
        select_statement
    };

}

// Export necessary function(s)
module.exports = {
    buildDesertSilver
};
