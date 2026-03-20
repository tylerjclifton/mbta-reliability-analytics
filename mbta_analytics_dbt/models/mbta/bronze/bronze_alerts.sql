{{
    config(
        materialized='incremental',
        unique_key=['alert_id', 'route', 'stop', 'ingestion_timestamp'],
        on_schema_change='sync_all_columns'
    )
}}

with source_data as (
    select
        alert_id,
        route,
        stop,
        active_period_start,
        active_period_end,
        duration_certainty,
        header,
        description,
        cause,
        effect,
        severity,
        created_at,
        updated_at,
        ingestion_timestamp,
        ingestion_source
    from `{{ env_var('DBT_PROJECT_ID', 'mbta-reliability-analytics') }}.staging.mbta_alerts`
    
    {% if is_incremental() %}
    -- Only load new records since the last run
    where ingestion_timestamp > (select max(ingestion_timestamp) from {{ this }})
    {% endif %}
)

select * from source_data
