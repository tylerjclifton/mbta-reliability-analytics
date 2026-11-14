{% macro eastern_time_from_text(column) -%}
  {#-
    A timestamp from Eastern local time written as text, with or without
    seconds ("2026-03-31 09:45", "2018-12-13 06:50:00"); NULL for anything
    else, such as the "NA" the MBTA's ferry trips use for a missing time.

    Usage:
      {{ eastern_time_from_text('actual_departure') }} AS actual_departure_at

    Compiles to:
      TIMESTAMP(
          COALESCE(
              SAFE.PARSE_DATETIME('%Y-%m-%d %H:%M:%S', actual_departure),
              SAFE.PARSE_DATETIME('%Y-%m-%d %H:%M', actual_departure)
          ),
          'America/New_York'
      )
  -#}
  TIMESTAMP(
      COALESCE(
          SAFE.PARSE_DATETIME('%Y-%m-%d %H:%M:%S', {{ column }}),
          SAFE.PARSE_DATETIME('%Y-%m-%d %H:%M', {{ column }})
      ),
      '{{ var("local_timezone") }}'
  )
{%- endmacro %}
