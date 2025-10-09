import { HandlerEvent } from "@netlify/functions";

declare global {
  namespace NodeJS {
    interface ProcessEnv {
      VITE_BIGQUERY_PROJECT_ID: string;
      GOOGLE_APPLICATION_CREDENTIALS_JSON: string;
      URL: string;
    }
  }
}