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
    let select_statement

    // If source key is alerts
    if (source_key === 'alerts') {

        // Create select statement
        select_statement = `
    WITH
    ${buildCteStandardized(source_key)},
    ${buildCteMapping(source_key)},
    
    stops AS (
        SELECT DISTINCT
            stop_id,
            stop_name
        FROM ${schema.data_sets.silver}.${schema.tables.silver.stops}
    ),

    alerts_with_stops AS (
        -- Case 1: Valid stop_id (5-6 digit number) - keep as is
        SELECT
            *
        FROM mapped_${source_key}
        WHERE
            REGEXP_CONTAINS(COALESCE(stop_id, ''), r'^[0-9]{5,6}$')
    
        UNION ALL

        -- Case 2: Invalid stop_id - extract stations from alert_description
        SELECT
            a.alert_id,
            a.alert_start,
            a.alert_end,
            a.alert_duration_certainty,
            a.route_id,
            s.stop_id,
            a.alert_header,
            a.alert_description,
            a.alert_cause,
            a.alert_effect,
            a.alert_service_effect,
            a.alert_severity,
            a.alert_lifecycle,
            a.alert_created_at,
            a.alert_updated_at,
            a.ingestion_timestamp,
            a.ingestion_source
        FROM mapped_${source_key} AS a
        CROSS JOIN stops AS s
        WHERE
            NOT REGEXP_CONTAINS(COALESCE(a.stop_id, ''), r'^[0-9]{5,6}$')
            AND UPPER(a.alert_description) LIKE '%' || UPPER(s.stop_name) || '%'

        UNION ALL
        
        -- Case 3: Invalid stop_id AND no description matches - try alert_header  
        SELECT 
            a.alert_id,
            a.alert_start,
            a.alert_end,
            a.alert_duration_certainty,
            a.route_id,
            s.stop_id,
            a.alert_header,
            a.alert_description,
            a.alert_cause,
            a.alert_effect,
            a.alert_service_effect,
            a.alert_severity,
            a.alert_lifecycle,
            a.alert_created_at,
            a.alert_updated_at,
            a.ingestion_timestamp,
            a.ingestion_source
        FROM mapped_${source_key} a  
        CROSS JOIN stops s
        WHERE
            NOT REGEXP_CONTAINS(COALESCE(a.stop_id, ''), r'^[0-9]{5,6}$')
            AND UPPER(a.alert_header) LIKE '%' || UPPER(s.stop_name) || '%'
            AND a.alert_id NOT IN (
                SELECT
                    alert_id
                FROM mapped_${source_key} ma
                CROSS JOIN stops st  
                WHERE
                    UPPER(ma.alert_description) LIKE '%' || UPPER(st.stop_name) || '%'
            )

        UNION ALL
        
        -- Case 4: No station matches anywhere - mark as 'Not Listed'
        SELECT 
            a.alert_id,
            a.alert_start,
            a.alert_end,
            a.alert_duration_certainty,
            a.route_id,
            'Not Listed' as stop_id,
            a.alert_header,
            a.alert_description,
            a.alert_cause,
            a.alert_effect,
            a.alert_service_effect,
            a.alert_severity,
            a.alert_lifecycle,
            a.alert_created_at,
            a.alert_updated_at,
            a.ingestion_timestamp,
            a.ingestion_source
        FROM mapped_${source_key} a
        WHERE
            NOT REGEXP_CONTAINS(COALESCE(a.stop_id, ''), r'^[0-9]{5,6}$')
            AND a.alert_id NOT IN (
                SELECT
                    alert_id
                FROM mapped_${source_key} ma
                CROSS JOIN stops st
                WHERE
                    UPPER(ma.alert_description) LIKE '%' || UPPER(st.stop_name) || '%'
                    OR UPPER(ma.alert_header) LIKE '%' || UPPER(st.stop_name) || '%'
            )
    )

    SELECT
        *
    FROM alerts_with_stops
    GROUP BY ALL;
        `;

    } else {
        // Standard processing
        select_statement = `
    WITH
    ${buildCteStandardized(source_key)},
    ${buildCteMapping(source_key)}

    SELECT
        *
    FROM mapped_${source_key};
        `;
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
