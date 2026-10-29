{% macro last_processed_snapshot() -%}
  {#-
    The newest bronze snapshot an incremental alerts table has already
    processed (MAX(last_seen_at) in the table being built), as a timestamp
    string ('YYYY-MM-DD HH:MM:SS.ffffff'), or none on a first build or
    --full-refresh. Shared by silver.mbta_alerts__base and
    silver.mbta_alerts__by_route.

    The model compiles it into its query as a literal, so BigQuery prunes
    bronze's ingested_at partitions; a subquery in the WHERE clause wouldn't.

    Usage:
      {%- set processed_through = last_processed_snapshot() -%}
      ...
      {%- if processed_through %}
      WHERE ingested_at > TIMESTAMP '{{ processed_through }}'
      {%- endif %}
  -#}
  {%- if is_incremental() and execute -%}
    {%- set result = run_query("SELECT FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%E6S', MAX(last_seen_at)) FROM " ~ this) -%}
    {{- return(result.columns[0].values()[0]) -}}
  {%- endif -%}
  {{- return(none) -}}
{%- endmacro %}
