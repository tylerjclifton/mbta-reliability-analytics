const {BigQuery} = require('google-cloud/bigquery');
const bigquery = new BigQuery();

exports.queryBigQuery = async (requestAnimationFrame, res) => {
    try {
        const query = `
            SELECT
                *
            FROM sonic-earth-456400-s3.mbta.gold_alerts
            LIMIT 100
        `;

        const options = {
            query: query,
            location: 'US',
        };

        const [job] = await bigquery.createQueryJob(options);
        console.log(`Job ${job.id} started.`);

        const [rows] = await job.getQueryResults();

        res.status(200).json(rows);
    } catch (error) {
        console.error(error);
        res.status(500).send('Error running BigQuery query');
    }
}