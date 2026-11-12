{% macro service_date(column, is_end=false) -%}
  {#-
    The MBTA service date a timestamp falls in. A service day runs from 3 AM
    to 3 AM Eastern (the MBTA posts its planned work from 3:00 to 2:59), so
    a train at 1 AM Saturday belongs to Friday.

    For the end of a span, pass is_end=true: an end exactly at a day's start
    (3:00 AM) belongs to the day before, since nothing ran in the new one.

    Usage:
      {{ service_date('period_start_at') }}             AS period_start_date
      {{ service_date('period_end_at', is_end=true) }}  AS period_end_date

    Compiles to:
      DATE(TIMESTAMP_SUB(period_start_at, INTERVAL 10800 SECOND), 'America/New_York')
      DATE(TIMESTAMP_SUB(period_end_at, INTERVAL 10801 SECOND), 'America/New_York')
  -#}
  DATE(
    TIMESTAMP_SUB({{ column }}, INTERVAL {{ 10801 if is_end else 10800 }} SECOND),
    '{{ var("local_timezone") }}'
  )
{%- endmacro %}
