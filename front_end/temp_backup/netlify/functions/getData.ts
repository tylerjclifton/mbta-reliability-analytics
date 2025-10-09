import { BigQuery } from '@google-cloud/bigquery';
import { Handler, HandlerEvent } from '@netlify/functions';

// Initialize BigQuery client
const bigquery = new BigQuery({
  projectId: process.env.VITE_BIGQUERY_PROJECT_ID,
  credentials: JSON.parse(process.env.GOOGLE_APPLICATION_CREDENTIALS_JSON || '{}'),
});

// Helper function to fetch data from BigQuery
async function queryBigQuery(query: string) {
  try {
    const [rows] = await bigquery.query({ query });
    return rows;
  } catch (error) {
    console.error('BigQuery Error:', error);
    throw error;
  }
}

export const handler: Handler = async (event: HandlerEvent) => {
  // Enable CORS for your domain
  const headers = {
    'Access-Control-Allow-Origin': process.env.URL || 'http://localhost:3000',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'GET, OPTIONS'
  };

  // Handle preflight requests
  if (event.httpMethod === 'OPTIONS') {
    return {
      statusCode: 204,
      headers,
      body: ''
    };
  }

  try {
    // Get query parameters
    const { table = 'shapes.silver' } = event.queryStringParameters || {};

    // Validate table name to prevent injection
    const validTables = ['shapes.silver', 'stops.silver', 'gold.rail_alerts'];
    if (!validTables.includes(table)) {
      throw new Error('Invalid table name');
    }

    // Construct and execute query
    const query = `
      SELECT *
      FROM \`${process.env.VITE_BIGQUERY_PROJECT_ID}.${table}\`
      LIMIT 1000
    `;

    const data = await queryBigQuery(query);

    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({ data })
    };
  } catch (error) {
    console.error('Function Error:', error);
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({ error: 'Internal Server Error' })
    };
  }
};