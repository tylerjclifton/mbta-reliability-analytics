// Import schemas
const {
    schema
} = require('includes/schemas');

function buildDesertGold(goldTableName) {
    // Validate the gold table exists in our schema
    const goldTable = schema.tables.gold[goldTableName];
    if (!goldTable) {
        throw new Error(`Gold table '${goldTableName}' not found in schema`);
    }

    // Get sources from the gold table configuration
    const sourcesConfig = goldTable.sources;
    if (!sourcesConfig || Object.keys(sourcesConfig).length === 0) {
        throw new Error(`No sources configured for gold table '${goldTableName}'`);
    }

    // Build the sources array with their join keys
    const sources = Object.keys(sourcesConfig).map(sourceKey => ({
        name: sourceKey,
        silverTable: schema.tables.silver[sourceKey],
        dimensions: schema.sources[sourceKey].dimensions,
        joinKey: sourcesConfig[sourceKey]
    }));

    // Build the SELECT statement
    const selectStatement = buildSelectQuery(sources, goldTable.name);

    return {
        selectStatement
    };
}

function buildSelectQuery(sources, goldTableName) {
    const primarySource = sources[0]; // First source is the main table
    const joinSources = sources.slice(1); // Remaining sources will be joined

    // Start building the query
    let query = ``;

    // Add all fields from all sources
    const allFields = [];
    sources.forEach(source => {
        source.dimensions.forEach(dimension => {
            allFields.push(`    ${source.name}.${dimension.alias}`);
        });
    });

    // Add metadata fields from primary source
    allFields.push(`    ${primarySource.name}.${schema.metadata.source}`);
    allFields.push(`    ${primarySource.name}.${schema.metadata.timestamp}`);

    query += allFields.join(',\n');

    // Add FROM clause with primary table
    const silverDataset = schema.dataSets.silver;
    query += `\nFROM ${silverDataset}.${primarySource.silverTable} AS ${primarySource.name}`;

    // Add JOIN clauses for additional sources
    joinSources.forEach(joinSource => {
        const joinCondition = getJoinCondition(primarySource, joinSource);
        query += `\nLEFT JOIN ${silverDataset}.${joinSource.silverTable} AS ${joinSource.name}`;
        query += `\n    ON ${joinCondition}`;
    });

    query += ';';
    return query;
}

function getJoinCondition(primarySource, joinSource) {
    // Use the join keys defined in the schema
    return `${primarySource.name}.${primarySource.joinKey} = ${joinSource.name}.${joinSource.joinKey}`;
}

// Usage:
// const result = buildDesertGold('systemAlerts');
// console.log(result.selectStatement);

module.exports = {
    buildDesertGold
};
