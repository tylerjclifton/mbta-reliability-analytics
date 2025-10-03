// Import config
const {
    config
} = require('includes/config');

// Get key from fields array
function getKeyField(source_key) {

    // Get fields array for source
    const fields_array = config.fields[source_key];

    // Determine key field (prefer *_id, fallback *_name)
    const key_field =
        fields_array.find(field => field.alias.toLowerCase().includes('_id')) ||
        fields_array.find(field => field.alias.toLowerCase().includes('_name'));

    // Return key field
    return key_field;

}

// Get raw values from fields array
function getRawFields(source_key) {

    // Throw error if config does not exist or does not have nested fields object
    if (!config || !config.fields) {
        throw new Error('Invalid config');
    }

    // Get source fields array
    const fields_array = config.fields[source_key];

    // Throw error if fields array does not exist or is empty
    if (!fields_array || fields_array.length === 0) {
        throw new Error(`No fields defined for source: ${source_key}`);
    }

    // Extract raw value from each field in fields array
    const raw_fields = fields_array.map(field => field.raw);

    // Return raw fields
    return raw_fields;

}

// Build delete statement for any medallion layer (bronze, silver, gold)
function buildDeleteStatement(medallion_layer, source_key) {

    // Get data set and table info
    const data_sets = config.data_sets;
    const tables = config.tables;

    // Initialize data set and table variables
    let source_data_set, destination_data_set, source_table, destination_table;

    // Initialize delete key variable
    let delete_key;

    switch (medallion_layer) {

        // When medallion layer is bronze
        case 'bronze': {

            // Get source fields array
            const fields_array = config.fields[source_key];

            // Throw error if fields array does not exist
            if (!fields_array || !fields_array.length) {
                throw new Error(`No fields defined for source: ${source_key}`);
            }

            // Determine key field for delete statement (prefer *_id, fallback *_name)
            delete_key = getKeyField(source_key);

            // Throw error if no valid delete key exists
            if (!delete_key) {
                throw new Error('No valid delete key found within fields');
            }

            // Get source data set and table
            source_data_set = data_sets[source_key];
            source_table = tables.staging[source_key];

            // Get destination data set and table
            destination_data_set = data_sets[source_key];
            destination_table = tables.bronze[source_key];

            // Break out of switch
            break;

        }

        // When medallion layer is silver
        case 'silver': {

            // Get fields array for source
            const fields_array = config.fields[source_key];

            // Throw error if fields array does not exist
            if (!fields_array || !fields_array.length) {
                throw new Error(`No fields defined for source: ${source_key}`);
            }

            // Determine key field for delete statement (prefer *_id, fallback *_name)
            delete_key = getKeyField(source_key);

            // Throw error if no valid delete key exists
            if (!delete_key) {
                throw new Error('No valid delete key found within fields');
            }

            // Get source data set and table
            source_data_set = data_sets[source_key];
            source_table = tables.bronze[source_key];

            // Get destination data set and table
            destination_data_set = data_sets[source_key];
            destination_table = tables.silver[source_key];

            // Break out of switch
            break;

        }

        // When medallion layer is gold
        case 'gold': {

            // Get gold table info
            const gold_table = tables.gold[source_key];

            // Throw error if gold table does not exist
            if (!gold_table) {
                throw new Error(`Gold table not found: ${source_key}`);
            }

            // Get primary source for gold table
            primary_source = config.tables.gold[source_key].sources[0];

            // Create array to hold combined fields
            const combined_fields = [];

            // Create set to hold previously seen fields
            const seen_aliases = new Set();

            // Iterate through listed sources for gold table
            gold_table.sources.forEach(src => {

                // Get source fields array
                const fields_array = config.fields[src];

                // Throw error if fields array does not exist
                if (!fields_array || !fields_array.length) {
                    throw new Error(`No fields defined for source: ${source_key}`);
                }

                // Iterate through each field in fields array
                fields_array.forEach(field => {

                    // If field's alias value has not been seen yet
                    if (!seen_aliases.has(field.alias)) {

                        // Add field to combined fields array
                        combined_fields.push(field);

                        // Add field to seen aliases array
                        seen_aliases.add(field.alias);

                    }

                });

            });

            // Determine key field for delete statement (prefer *_id, fallback *_name)
            delete_key = getKeyField(primary_source);

            // Throw error if no valid delete key exists
            if (!delete_key) {
                throw new Error('No valid delete key found within fields');
            }

            // Get source data set and table
            source_data_set = data_sets[primary_source]; // Use first source for delete reference
            source_table = tables.silver[primary_source]; // Use first source for delete reference

            // Get destination data set and table
            destination_data_set = 'gold';
            destination_table = gold_table.name;

            // Break out of switch
            break;

        }

        // When no valid medallion layer is provided throw error
        default:
            throw new Error('Bad medallion_layer: ' + medallion_layer);
    }

    // Build where clause for delete statement
    const whereClause =

        // Check if medallion layer is bronze or silver
        medallion_layer === 'bronze' ?

        // If bronze
        `
        ${delete_key.raw} IN (
            SELECT DISTINCT
                ${delete_key.raw}
            FROM ${source_data_set}.${source_table}
        )
        `
        // Or
        :
        // If not bronze
        `
        ${delete_key.alias} IN (
            SELECT DISTINCT
                ${delete_key.alias}
            FROM ${source_data_set}.${source_table}
        )
        `

    // Return delete statement
    return `
    DELETE FROM ${destination_data_set}.${destination_table}
    WHERE${whereClause};
    `

}

// Build desert statement for bronze layer
function buildDesertBronze(source_key) {

    // Get source data set and table
    const source_data_set = config.data_sets[source_key];
    const source_table = config.tables.staging[source_key];

    // Get raw values from source fields array
    const raw_fields = getRawFields(source_key);

    // Throw error if raw fields array is empty or doesn't exist
    if (!raw_fields || raw_fields.length === 0) {
        throw new Error(`No fields defined for source: ${source_key}`);
    }

    // Build delete statement
    const delete_statement = buildDeleteStatement('bronze', source_key);

    // Build select statement
    const select_statement = `
    SELECT
        ${raw_fields.join(',\n        ')}
    FROM ${source_data_set}.${source_table};
    `;

    // Return statements
    return {
        delete_statement,
        select_statement
    };

}

// Build base CTE (renaming + casting)
function buildCteBase(source_key) {

    // Get source data set and table
    const source_data_set = config.data_sets[source_key];
    const source_table = config.tables.bronze[source_key];

    // Get source fields array
    const fields_array = config.fields[source_key];

    // Throw error if fields array is empty or doesn't exist
    if (!fields_array || fields_array.length === 0) {
        throw new Error(`No fields defined for source: ${source_key}`);
    }

    // Build rows for renaming and casting each field in fields array
    const rows = fields_array.map(
        field => {
            if (field.type === 'DATE') {
                return `CAST(REGEXP_EXTRACT(CAST(${field.raw} AS STRING), r"^\\d{4}-\\d{2}-\\d{2}") AS DATE) AS ${field.alias}`
            } else {
                return `CAST(${field.raw} AS ${field.type}) AS ${field.alias}`
            }
        }
    );

    // Return base CTE
    return `
    base_${source_key} AS (
        SELECT
            ${rows.join(',\n            ')}
        FROM ${source_data_set}.${source_table}
        GROUP BY ALL
    )`;

}

// Build mapping CTE (applying taxonomy)
function buildCteMapping(source_key) {

    // Get source fields array
    const fields_array = config.fields[source_key];

    // Iterate through fields array and apply taxonomy rules where available
    const mapped_rows = fields_array.map(f => {

        // Check if taxonomy exists for this source and field alias
        if (config.taxonomy[source_key] && config.taxonomy[source_key][f.alias]) {

            // Retrieve the taxonomy mapping for this field
            const mapping = config.taxonomy[source_key][f.alias];

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
        FROM base_${source_key}
    )`;

}

// Build desert statement for silver layer
function buildDesertSilver(source_key) {

    // Build delete statement
    const delete_statement = buildDeleteStatement('silver', source_key);

    // Initialize select statement variable
    let select_statement;

    // If source key is alerts
    if (source_key === 'alerts') {

        // Get stops data set and table
        const stops_data_set = config.data_sets.stops;
        const stops_table = config.tables.silver.stops;

        // Get alerts and stops field arrays
        const alerts_fields = config.fields['alerts'];
        const stops_fields = config.fields['stops'];

        // Get final alerts fields
        const final_alerts_fields = alerts_fields.map(field => `${field.alias}`)

        // Get fields for alerts with mapped stops join
        const final_alert_fields_no_stop = alerts_fields
            .map(field => {
                if (field.alias === 'stop_id') {
                    return "'Unavailable' AS stop_id";
                }
                return `${field.alias}`;
            });

        // Get stops id and name fields
        const stops_id_field = stops_fields.find(field => field.alias.toLowerCase().includes('_id')).alias;
        const stops_name_field = stops_fields.find(field => field.alias.toLowerCase().includes('_name')).alias;

        // Create select statement for alerts
        select_statement = `
    WITH
    ${buildCteBase(source_key)},

    stops_lookup AS (
        SELECT DISTINCT
            ${stops_id_field},
            ${stops_name_field}
        FROM ${stops_data_set}.${stops_table}
    ),

    alerts_with_valid_stops AS (
        SELECT
            ${final_alerts_fields.join(',\n            ')}
        FROM base_${source_key}
        WHERE
            REGEXP_CONTAINS(stop_id, r'^[0-9]{5,6}$')
    ),

    alerts_without_valid_stops AS (
        SELECT
            ${final_alert_fields_no_stop.join(',\n            ')}
        FROM base_${source_key}
        WHERE
            NOT REGEXP_CONTAINS(stop_id, r'^[0-9]{5,6}$')
        GROUP BY ALL
    )

    SELECT
        *
    FROM alerts_with_valid_stops

    UNION ALL
    
    SELECT
        *
    FROM alerts_without_valid_stops;
        `;

    } else if (source_key in config.taxonomy) {
        // Standard processing
        select_statement = `
    WITH
    ${buildCteBase(source_key)},
    ${buildCteMapping(source_key)}

    SELECT
        *
    FROM mapped_${source_key};
        `;
    } else {
        select_statement = `
    WITH
    ${buildCteBase(source_key)}

    SELECT
        *
    FROM base_${source_key};
    `
    }

    // Return statements
    return {
        delete_statement,
        select_statement
    };

}

// Find common keys between two sources for joining, only _id fields
function findJoinKeys(sourceA, sourceB) {
    const fieldsA = config.fields[sourceA]
        .map(f => f.alias)
        .filter(alias => alias.toLowerCase().includes('_id')); // only _id fields
    const fieldsB = config.fields[sourceB]
        .map(f => f.alias)
        .filter(alias => alias.toLowerCase().includes('_id')); // only _id fields
    return fieldsA.filter(f => fieldsB.includes(f)); // keep order of sourceA
}

// Build desert statement for gold layer
function buildDesertGold(gold_key) {
    const gold_table = config.tables.gold[gold_key];
    if (!gold_table) throw new Error(`No gold table found for ${gold_key}`);
    if (!gold_table.sources || gold_table.sources.length === 0) throw new Error(`No sources defined for gold table: ${gold_key}`);

    const sources = gold_table.sources;

    // Build delete statement
    const delete_statement = buildDeleteStatement('gold', gold_key);

    // Build unique field list and join information
    const unique_fields = [];
    const fieldSet = new Set();
    const joinKeysUsed = new Set();

    sources.forEach((source, index) => {
        const fieldsArray = config.fields[source];
        fieldsArray.forEach(field => {
            const alias = `${field.alias}`;

            // Skip join keys if already used in previous sources
            if (index > 0) {
                const isJoinKey = sources.slice(0, index).some(prevSource =>
                    config.fields[prevSource].some(prevField => prevField.alias === field.alias)
                );

                if (isJoinKey) {
                    joinKeysUsed.add(field.alias);
                    return;
                }
            }

            if (!fieldSet.has(alias)) {
                unique_fields.push({
                    source,
                    alias,
                    raw: field.alias
                });
                fieldSet.add(alias);
            }
        });
    });

    // Build SELECT fields
    const select_fields = unique_fields.map(f => `${f.source}.${f.raw} AS ${f.alias}`);

    // Build JOIN statements
    let joinStatements = '';
    const baseSource = sources[0];

    for (let i = 1; i < sources.length; i++) {
        const nextSource = sources[i];
        const joinKeys = findJoinKeys(baseSource, nextSource);
        if (!joinKeys.length) throw new Error(`No common keys found between ${baseSource} and ${nextSource}`);

        const onClause = joinKeys.map(k => `${baseSource}.${k} = ${nextSource}.${k}`).join(' AND ');
        joinStatements += `${i > 1 ? '\n' : ''}${i > 1 ? `    ` : ``}LEFT JOIN ${config.data_sets[nextSource]}.${config.tables.silver[nextSource]} AS ${nextSource} 
        ON ${onClause}`;
    }

    const select_statement = `
    SELECT
        ${select_fields.join(',\n        ')}
    FROM ${config.data_sets[baseSource]}.${config.tables.silver[baseSource]} AS ${baseSource}
    ${joinStatements};`;

    return {
        delete_statement,
        select_statement
    };
}

// Export necessary function(s)
module.exports = {
    buildDesertBronze,
    buildDesertSilver,
    buildDesertGold
}
