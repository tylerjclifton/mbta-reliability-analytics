const {
    schema
} = require('includes/schema');

// Get fields from a source, optionally with a prefix
function getFieldsForSelect(sourceKey, prefix) {
    const fields = schema.fields[sourceKey];
    if (!fields) throw new Error(`No fields defined for ${sourceKey}`);
    return fields.map(f => `${prefix || sourceKey}.${f.alias} AS ${prefix || sourceKey}_${f.alias}`);
}

// Find common keys between two sources for joining
function findJoinKeys(sourceA, sourceB) {
    const fieldsA = schema.fields[sourceA].map(f => f.alias);
    const fieldsB = schema.fields[sourceB].map(f => f.alias);
    return fieldsA.filter(f => fieldsB.includes(f));
}

// Build gold desert (delete + insert) dynamically from sources
function buildDesertGold(goldKey) {
    const goldEntry = schema.tables.gold[goldKey];
    if (!goldEntry) throw new Error(`No gold table found for ${goldKey}`);

    const sources = goldEntry.sources;
    if (!sources || sources.length === 0) throw new Error(`No sources defined for gold table ${goldKey}`);

    // Collect all fields dynamically from listed sources
    const uniqueFields = [];
    const fieldSet = new Set();
    sources.forEach(src => {
        schema.fields[src].forEach(f => {
            const alias = `${src}_${f.alias}`;
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

    // Build delete statement using first source's ID field
    const firstSource = sources[0];
    const deleteKey = schema.fields[firstSource].find(f => f.alias.toLowerCase().includes('_id')) ||
        schema.fields[firstSource].find(f => f.alias.toLowerCase().includes('_name'));
    if (!deleteKey) throw new Error(`No delete key found for ${firstSource}`);

    const deleteStatement = `
DELETE FROM ${schema.data_sets.gold}.${goldEntry.name || goldKey}
WHERE ${deleteKey.alias} IN (
    SELECT DISTINCT ${deleteKey.alias} 
    FROM ${schema.data_sets.silver}.${schema.tables.silver[firstSource]}
);`;

    // Build select + joins
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
    return `
-- Delete existing records
${deleteStatement}

-- Insert joined data
INSERT INTO ${schema.data_sets.gold}.${goldEntry.name || goldKey} (
    ${uniqueFields.map(f => f.alias).join(', ')}
)
SELECT
    ${selectFields.join(',\n    ')}
FROM ${schema.data_sets.silver}.${schema.tables.silver[baseSource]} AS ${baseSource}
${joinStatements};
  `.trim();
}

module.exports = {
    buildDesertGold
};
