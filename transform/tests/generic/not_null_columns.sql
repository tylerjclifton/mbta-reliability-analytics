{% test not_null_columns(model, columns) %}
  {#-
    Required-fields test: no row has a NULL in any of `columns`. Fails with
    one row per column that has NULLs, and how many it has.

    Takes the place of dbt's not_null on each column: every query bills at
    least 10 MB, so one query for all of a model's columns costs one minimum
    instead of one per column (decision 0021).

    Usage (model-level, in a properties yml):
      data_tests:
        - not_null_columns:
            arguments:
              columns: [service_date, line_name]
  -#}
SELECT
    column_name,
    null_rows
FROM (
    SELECT
        {%- for column in columns %}
        COUNTIF({{ column }} IS NULL) AS {{ column }}{{ ',' if not loop.last }}
        {%- endfor %}
    FROM {{ model }}
)
UNPIVOT (null_rows FOR column_name IN ({{ columns | join(', ') }}))
WHERE null_rows > 0
{% endtest %}
