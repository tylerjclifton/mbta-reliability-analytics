// Import schema
const {
    schema
} = require('includes/schema');

// Get fields from a source, optionally with a prefix
function getFieldsForSelect(source_key, prefix) {
    const fields = schema.fields[source_key];
    if (!fields) throw new Error(`No fields defined for ${source_key}`);
    return fields.map(f => `${prefix || source_key}.${f.alias} AS ${prefix || source_key}_${f.alias}`);
}

// Find common keys between two sources for joining
function findJoinKeys(sourceA, sourceB) {
    const fieldsA = schema.fields[sourceA].map(f => f.alias);
    const fieldsB = schema.fields[sourceB].map(f => f.alias);
    return fieldsA.filter(f => fieldsB.includes(f));
}

// Build gold desert (delete + insert) dynamically from sources
function buildDesertGold(gold_key) {
    const goldEntry = schema.tables.gold[gold_key];
    if (!goldEntry) throw new Error(`No gold table found for ${gold_key}`);

    const sources = goldEntry.sources;
    if (!sources || sources.length === 0) throw new Error(`No sources defined for gold table ${gold_key}`);

    // Collect all fields dynamically from listed sources, avoiding duplicates for join keys
    const uniqueFields = [];
    const fieldSet = new Set();
    const joinKeysUsed = new Set();

    sources.forEach((src, index) => {
        schema.fields[src].forEach(f => {
            const alias = `${src}_${f.alias}`;

            // For join keys, only include from the first source that has it
            if (index > 0) {
                const isJoinKey = sources.slice(0, index).some(prevSrc =>
                    schema.fields[prevSrc].some(prevField => prevField.alias === f.alias)
                );

                if (isJoinKey) {
                    joinKeysUsed.add(f.alias);
                    return; // Skip this field as it's already included from a previous source
                }
            }

            if (!fieldSet.has(alias)) {
                uniqueFields.push({
                    src,
                    alias,
                    raw: f.alias
                });
                fieldSet.add(alias);
            }
        });
    });

    // Build delete statement using first source's ID field (same logic as buildDeleteStatement)
    const firstSource = sources[0];
    const deleteKey = schema.fields[firstSource].find(f => f.alias.toLowerCase().includes('_id')) ||
        schema.fields[firstSource].find(f => f.alias.toLowerCase().includes('_name'));
    if (!deleteKey) throw new Error(`No delete key found for ${firstSource}`);

    const deleteStatement = `
DELETE FROM ${schema.data_sets.gold}.${goldEntry.name || gold_key}
WHERE ${deleteKey.alias} IN (
  SELECT DISTINCT ${deleteKey.alias}
  FROM ${schema.data_sets.silver}.${schema.tables.silver[sources[0]]}
);`;

    // Build select + joins in source order
    let selectFields = uniqueFields.map(f => `${f.src}.${f.raw} AS ${f.alias}`);
    let joinStatements = '';
    let baseSource = sources[0];

    for (let i = 1; i < sources.length; i++) {
        const nextSource = sources[i];
        const joinKeys = findJoinKeys(baseSource, nextSource);
        if (!joinKeys.length) throw new Error(`No common keys found between ${baseSource} and ${nextSource}`);

        const onClause = joinKeys.map(k => `${baseSource}.${k} = ${nextSource}.${k}`).join(' AND ');
        joinStatements += `\nLEFT JOIN ${schema.data_sets.silver}.${schema.tables.silver[nextSource]} AS ${nextSource} ON ${onClause}`;
    }

    // Final SQL
    const select_statement = `
SELECT
  ${selectFields.join(',\n  ')}
FROM ${schema.data_sets.silver}.${schema.tables.silver[baseSource]} AS ${baseSource}
${joinStatements}`.trim();

    return {
        delete_statement: deleteStatement.trim(),
        select_statement: select_statement
    };
}

// Export necessary function(s)
module.exports = {
    buildDesertGold
};
