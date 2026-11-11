{# SUPPORT users only see customers from the countries mapped to them (GOVERNANCE.SUPPORT_COUNTRY_MAP). #}
{% macro attach_row_access(column) %}
  ALTER ICEBERG TABLE {{ this }} ADD ROW ACCESS POLICY LAKEHOUSE.GOVERNANCE.RAP_SUPPORT_COUNTRY ON ({{ column }})
{% endmacro %}
