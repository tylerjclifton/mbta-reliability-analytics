{#
  Silver Layer - Combined MBTA Data
  
  Joins all MBTA bronze sources together:
  - bronze_alerts (base table - grain: alert_id, route_id)
  - bronze_routes (lookup for route details)
  
  Applies type casting and field aliasing.
  Uses explicit DELETE + INSERT pattern.
#}

{{
    config(
        materialized='incremental',
        on_schema_change='sync_all_columns'
    )
}}

{# Execute DELETE before INSERT when incremental #}
{% if is_incremental() %}
  {% set project_id = env_var('DBT_PROJECT_ID', 'mbta-reliability-analytics') %}
  {% set delete_sql %}
    DELETE FROM `{{ project_id }}.{{ target.dataset }}.mbta_silver`
    WHERE alert_id IN (SELECT DISTINCT alert_id FROM `{{ project_id }}.{{ target.dataset }}.mbta_bronze_alerts`)
  {% endset %}
  
  {% do run_query(delete_sql) %}
{% endif %}

SELECT
    -- Alert fields (from bronze_alerts)
    CAST(REGEXP_EXTRACT(CAST(a.active_period_start AS STRING), r"^\d{4}-\d{2}-\d{2}") AS DATE) AS alert_start_date,
    CAST(REGEXP_EXTRACT(CAST(a.active_period_end AS STRING), r"^\d{4}-\d{2}-\d{2}") AS DATE) AS alert_end_date,
    CAST(a.alert_id AS STRING) AS alert_id,
    CAST(a.route AS STRING) AS route_id,
    CAST(a.header AS STRING) AS alert_header,
    CAST(a.description AS STRING) AS alert_description,
    CAST(a.cause AS STRING) AS alert_cause,
    CAST(a.effect AS STRING) AS alert_effect,
    CAST(a.severity AS INT64) AS alert_severity,
    CAST(a.duration_certainty AS STRING) AS alert_duration_certainty,
    CAST(REGEXP_EXTRACT(CAST(a.created_at AS STRING), r"^\d{4}-\d{2}-\d{2}") AS DATE) AS alert_created_at,
    CAST(REGEXP_EXTRACT(CAST(a.updated_at AS STRING), r"^\d{4}-\d{2}-\d{2}") AS DATE) AS alert_updated_at,
    
    -- Route fields (from bronze_routes)
    CAST(r.long_name AS STRING) AS route_name,
    CAST(r.description AS STRING) AS route_description,
    CAST(r.route_type AS STRING) AS route_type,
    CAST(r.color AS STRING) AS route_color,
    CAST(r.direction_destinations AS STRING) AS route_destinations,
    
    -- Metadata
    CAST(a.ingestion_source AS STRING) AS ingestion_source,
    CAST(a.ingestion_timestamp AS TIMESTAMP) AS ingestion_timestamp

FROM {{ ref('mbta_bronze_alerts') }} AS a
LEFT JOIN {{ ref('mbta_bronze_routes') }} AS r
    ON a.route = r.route_id
