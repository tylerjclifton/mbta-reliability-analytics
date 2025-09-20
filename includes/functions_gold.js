// Import schema and utilities
const {
    schema
} = require('includes/schema');
const functions_utilities = require('./functions_utilities'); // Add this line

// Find common keys between two sources for joining
function findJoinKeys(sourceA, sourceB) {
    const fieldsA = schema.fields[sourceA].map(f => f.alias);
    const fieldsB = schema.fields[sourceB].map(f => f.alias);
    return fieldsA.filter(f => fieldsB.includes(f));
}

// Build desert statement for gold layer
function buildDesertGold(gold_key) {
    const gold_table = schema.tables.gold[gold_key];
    if (!gold_table) throw new Error(`No gold table found for ${gold_key}`);
    if (!gold_table.sources || gold_table.sources.length === 0) throw new Error(`No sources defined for gold table: ${gold_key}`);

    const sources = gold_table.sources;

    // Build delete statement
    const delete_statement = functions_utilities.buildDeleteStatement('gold', gold_key);

    // Build unique field list and join information
    const unique_fields = [];
    const fieldSet = new Set();
    const joinKeysUsed = new Set();

    sources.forEach((source, index) => {
        const fieldsArray = schema.fields[source];
        fieldsArray.forEach(field => {
            const alias = `${field.alias}`;

            // Skip join keys if already used in previous sources
            if (index > 0) {
                const isJoinKey = sources.slice(0, index).some(prevSource =>
                    schema.fields[prevSource].some(prevField => prevField.alias === field.alias)
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
        joinStatements += `\nLEFT JOIN ${schema.data_sets.silver}.${schema.tables.silver[nextSource]} AS ${nextSource} 
        ON ${onClause}`;
    }

    const select_statement = `
    SELECT
        ${select_fields.join(',\n        ')}
    FROM ${schema.data_sets.silver}.${schema.tables.silver[baseSource]} AS ${baseSource}
    ${joinStatements};`;

    return {
        delete_statement,
        select_statement
    };
}

module.exports = {
    buildDesertGold
};
