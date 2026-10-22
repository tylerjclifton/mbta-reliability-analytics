{% macro keep_latest_version(key_columns) -%}
  {#-
    Keep only the most recently ingested row for each key.

    Bronze tables are append-only, so the same record (an alert, a service day,
    a weather day) appears once per ingest run that saw it. Silver views use
    this to collapse those versions down to the latest one.

    Usage — placed after FROM/WHERE in a query over a bronze table:
      SELECT * FROM {{ source('bronze', 'mbta_ridership') }}
      {{ keep_latest_version(['service_date', 'route_or_line']) }}

    Compiles to:
      QUALIFY ROW_NUMBER() OVER (
          PARTITION BY service_date, route_or_line ORDER BY ingested_at DESC
      ) = 1
  -#}
  QUALIFY ROW_NUMBER() OVER (
      PARTITION BY {{ key_columns | join(', ') }} ORDER BY ingested_at DESC
  ) = 1
{%- endmacro %}
