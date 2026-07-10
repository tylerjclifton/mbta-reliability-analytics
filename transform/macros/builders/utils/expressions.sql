{#
  Expression Macros
  Generate SQL expressions for field casting, joins, select lists, etc.
#}


{% macro cast_as_date(field) -%}
    CAST(REGEXP_EXTRACT(CAST({{ field }} AS STRING), r'^\d{4}-\d{2}-\d{2}') AS DATE)
{%- endmacro %}


{% macro cast_field(field, type) -%}
    {%- if type | lower == 'date' -%}
        {{ cast_as_date(field) }}
    {%- else -%}
        CAST({{ field }} AS {{ type | upper }})
    {%- endif -%}
{%- endmacro %}
