{% macro null_if_epoch(column) -%}
  {#-
    Return a timestamp, or NULL if it's the MBTA API's "not set" placeholder.

    The alerts API sends the Unix epoch (1970-01-01) rather than null for an
    unset time, e.g. an active period with no posted end. Anything before
    1970-01-02 is treated as that placeholder.

    Usage:
      {{ null_if_epoch('posted_end_at') }} AS posted_end_at

    Compiles to:
      IF(posted_end_at > TIMESTAMP '1970-01-02', posted_end_at, NULL)
  -#}
  IF({{ column }} > TIMESTAMP '1970-01-02', {{ column }}, NULL)
{%- endmacro %}
