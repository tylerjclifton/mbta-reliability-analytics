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
