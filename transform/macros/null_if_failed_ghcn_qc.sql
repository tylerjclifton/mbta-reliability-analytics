{% macro null_if_failed_ghcn_qc(element) -%}
  {#-
    Return a GHCN-Daily value, or NULL if NOAA's quality control flagged it.

    Each GHCN element column (e.g. tmax) has a companion <element>_attributes
    column holding comma-separated flags: "measurement,quality,source[,time]".
    An empty quality flag (2nd position) means the value passed every check;
    any letter means it failed one (see NOAA's GHCN-Daily readme, Table 1).

    Usage:
      {{ null_if_failed_ghcn_qc('tmax') }} AS tmax_tenths_c

    Compiles to:
      IF(COALESCE(SPLIT(tmax_attributes, ',')[SAFE_OFFSET(1)], '') = '', tmax, NULL)
  -#}
  IF(COALESCE(SPLIT({{ element }}_attributes, ',')[SAFE_OFFSET(1)], '') = '', {{ element }}, NULL)
{%- endmacro %}
