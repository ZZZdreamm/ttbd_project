{# Use SILVER / GOLD exactly, not <target_schema>_SILVER. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
  {{ (custom_schema_name or target.schema) | trim | upper }}
{%- endmacro %}
