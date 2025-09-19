const {
    schema
} = require('includes/schema');

function getSourceKeys() {
    return Object.keys(schema.sources);
}

function buildDeleteStatement(medallionLayer, sourceKey) {
    const sourceBlock = schema.sources;
    let dims = [];

    if (medallionLayer === 'bronze') {
        dims = sourceBlock[sourceKey].dimensions;
    } else {
        const allSourceObjects = Object.values(sourceBlock);
        const arrayOfDimArrays = allSourceObjects.map(f => f.dimensions || []);
        dims = [].concat(...arrayOfDimArrays);
    }

    if (!dims || dims.length === 0) {
        throw new Error('No dimensions to derive delete key');
    }

    const deleteKey =
        dims.find(d => d.alias === 'date' && d.type === 'DATE') ||
        dims.find(d => d.alias === 'start_date' && d.type === 'DATE') ||
        dims.find(d => d.type === 'DATE') ||
        dims.find(d => d.alias.toLowerCase().includes('_id')) ||
        dims.find(d => d.alias.toLowerCase().includes('_name'));

    if (!deleteKey) {
        throw new Error('No valid delete key found within dimensions');
    }

    let startRaw = null,
        endRaw = null;

    dims.forEach(d => {
        if (d.alias === 'start_date') startRaw = d.raw;
        if (d.alias === 'end_date') endRaw = d.raw;
    });

    const ds = schema.dataSets;
    const tbl = schema.tables;

    const ingestionSource = schema.metadata.source;

    let sourceDataSet, destinationDataSet, sourceTable, destinationTable, whereClause;

    switch (medallionLayer) {
        case 'bronze':
            sourceDataSet = ds.staging;
            destinationDataSet = ds.bronze;
            sourceTable = tbl.staging[sourceKey];
            destinationTable = tbl.bronze[sourceKey];

            whereClause = `
        ${deleteKey.raw} IN (
            SELECT DISTINCT
                ${deleteKey.raw}
            FROM ${sourceDataSet}.${sourceTable}
        )`;
            break;

        case 'silver': {
            sourceDataSet = ds.bronze;
            destinationDataSet = ds.silver;
            sourceTable = tbl.bronze[sourceKey];
            destinationTable = tbl.silver[sourceKey];

            let destinationDeleteKey = deleteKey.alias;
            if (deleteKey.alias === 'start_date' && deleteKey.type === 'DATE') {
                destinationDeleteKey = 'date';
            }

            if (startRaw && endRaw) {
                whereClause = `
        ${destinationDeleteKey} BETWEEN (
            SELECT MIN(${startRaw}) FROM ${sourceDataSet}.${sourceTable}
        ) AND (
            SELECT MAX(${endRaw}) FROM ${sourceDataSet}.${sourceTable}
        )`;
            } else {
                whereClause = `
        ${destinationDeleteKey} IN (
            SELECT DISTINCT ${deleteKey.raw}
            FROM ${sourceDataSet}.${sourceTable}
        )`;
            }

            if (!ingestionSource) {
                throw new Error('Ingestion source not defined in metadata.source');
            }

            whereClause += `
        AND ${ingestionSource} LIKE '%${sourceKey}%'`;
            break;
        }

        case 'gold':
            sourceDataSet = ds.silver;
            destinationDataSet = ds.gold;
            sourceTable = tbl.silver[sourceKey];
            destinationTable = tbl.gold[sourceKey] || tbl.gold[sourceKey]; // fallback

            if (startRaw || endRaw) {
                whereClause = `
        date IN (
            SELECT DISTINCT date
            FROM ${sourceDataSet}.${sourceTable}
        ) AND ${ingestionSource} LIKE '%${sourceKey}%'`;
            } else {
                whereClause = `
        ${deleteKey.alias} IN (
            SELECT DISTINCT ${deleteKey.alias}
            FROM ${sourceDataSet}.${sourceTable}
        ) AND ${ingestionSource} LIKE '%${sourceKey}%'`;
            }
            break;

        default:
            throw new Error('Bad medallionLayer: ' + medallionLayer);
    }

    return (
        `
    DELETE FROM ${destinationDataSet}.${destinationTable}
    WHERE${whereClause};
    `.trim()
    );
}

function getRawFields(sourceKey) {
    if (!schema || !schema.sources)
        throw new Error('Invalid schema');

    const sourceObject = schema.sources[sourceKey];
    if (!sourceObject)
        throw new Error('Unknown sourceKey: ' + sourceKey);

    const dimensionsArray = sourceObject.dimensions;
    const metricsArray = sourceObject.metrics || [];

    const rawDimensions = dimensionsArray.map(d => d.raw);
    const rawMetrics = metricsArray.map(m => m.raw);

    return {
        rawDimensions,
        rawMetrics
    };
}

function getFinalFields() {
    const sourcesObj = schema.sources;
    const contains = (array, value) => array.includes(value);
    const skip = ['start_date', 'end_date'];

    const finalDimensions = [];
    const finalMetrics = [];
    const finalMetadata = [];

    let skippedDateRangeField = false;

    Object.values(sourcesObj).forEach(src => {
        (src.dimensions || []).forEach(f => {
            if (skip.includes(f.alias)) {
                skippedDateRangeField = true;
                return;
            }
            if (!contains(finalDimensions, f.alias)) finalDimensions.push(f.alias);
        });
    });

    if (skippedDateRangeField) {
        if (!contains(finalDimensions, 'date')) {
            finalDimensions.unshift('date');
        }
    } else {
        const index = finalDimensions.indexOf('date');
        if (index > 0) {
            finalDimensions.splice(index, 1);
            finalDimensions.unshift('date');
        }
    }

    Object.values(sourcesObj).forEach(src => {
        (src.metrics || []).forEach(f => {
            if (!contains(finalMetrics, f.alias)) finalMetrics.push(f.alias);
        });
    });

    const meta = schema.metadata || {};
    if (meta.source) finalMetadata.push(meta.source);
    if (meta.timestamp) finalMetadata.push(meta.timestamp);

    return {
        finalDimensions,
        finalMetrics,
        finalMetadata
    };
}

module.exports = {
    getSourceKeys,
    buildDeleteStatement,
    getRawFields,
    getFinalFields
};
