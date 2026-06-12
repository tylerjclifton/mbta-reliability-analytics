{#
  Resolver Macros
  Extract information from configs and metadata.
#}

{% macro get_partner_config(partner_key) %}
  {# Returns the full config object for a partner #}
  {# Dynamically calls get_{partner_key}_config() macro #}
  {% set macro_name = 'get_' ~ partner_key ~ '_config' %}
  {% set config_macro = context[macro_name] %}
  {% do return(config_macro()) %}
{% endmacro %}

{% macro get_partner_sources(partner_key) %}
  {# Returns the sources object for a partner #}
  {% set partner_config = get_partner_config(partner_key) %}
  {% do return(partner_config.sources) %}
{% endmacro %}

{% macro get_partner_joins(partner_key) %}
  {# Returns the join configuration array for a partner #}
  {% set partner_config = get_partner_config(partner_key) %}
  {% do return(partner_config.joins) %}
{% endmacro %}

{% macro get_base_source(partner_key) %}
  {#
    Resolve the primary/base source for silver models.
    Prefer explicit joins[*].base_source when present, otherwise pick first non-lookup source.
  #}
  {% set partner_joins = get_partner_joins(partner_key) %}
  {% if partner_joins | length > 0 and partner_joins[0].base_source is defined %}
    {% do return(partner_joins[0].base_source) %}
  {% endif %}

  {% set partner_sources = get_partner_sources(partner_key) %}
  {% for source_key, source_definition in partner_sources.items() %}
    {% if not source_definition.lookup %}
      {% do return(source_key) %}
    {% endif %}
  {% endfor %}

  {% do exceptions.raise_compiler_error("No base source found for partner: " ~ partner_key) %}
{% endmacro %}

{% macro get_source_definition(partner_key, source_key) %}
  {# Returns the definition for a specific source #}
  {% set partner_sources = get_partner_sources(partner_key) %}
  {% do return(partner_sources[source_key]) %}
{% endmacro %}

{% macro get_source_grain_keys(partner_key, source_key) %}
  {# Get the grain keys for a specific source #}
  {% set source_definition = get_source_definition(partner_key, source_key) %}
  {% do return(source_definition.grain_keys) %}
{% endmacro %}

{% macro get_source_fields(partner_key, source_key) %}
  {# Returns the fields object for a source #}
  {% set source_definition = get_source_definition(partner_key, source_key) %}
  {% do return(source_definition.fields) %}
{% endmacro %}

{% macro get_raw_fields(partner_key, source_key) %}
  {# Returns ordered raw field names (dimensions first, then metrics) for bronze selects #}
  {% set source_fields = get_source_fields(partner_key, source_key) %}
  {% set raw_fields = [] %}

  {% for field in source_fields.dimensions %}
    {% do raw_fields.append(field.raw) %}
  {% endfor %}

  {% for field in source_fields.metrics %}
    {% do raw_fields.append(field.raw) %}
  {% endfor %}

  {% do return(raw_fields) %}
{% endmacro %}

{% macro get_source_dimension_definitions(partner_key, source_key) %}
  {# Returns the dimension definitions array for a source #}
  {% set source_fields = get_source_fields(partner_key, source_key) %}
  {% do return(source_fields.dimensions) %}
{% endmacro %}

{% macro get_source_metric_definitions(partner_key, source_key) %}
  {# Returns the metric definitions array for a source #}
  {% set source_fields = get_source_fields(partner_key, source_key) %}
  {% do return(source_fields.metrics) %}
{% endmacro %}
