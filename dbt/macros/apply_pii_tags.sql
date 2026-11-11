{#
  Explicit, metadata-driven tagging: every column with `meta: {pii_type: ...}` in the model YAML
  gets LAKEHOUSE.GOVERNANCE.PII_TYPE. Masking follows automatically (policies are bound to the tag).
  Runs after every build (tables are recreated, so tags are re-applied).
#}
{% macro apply_pii_tags() %}
  {%- set allowed = ['NAME', 'EMAIL', 'PHONE', 'ADDRESS', 'DOB', 'IP', 'CARD'] -%}
  {%- set row_access_keys = ['COUNTRY', 'SHIPPING_COUNTRY'] -%}
  {%- for col_name, col in model.columns.items() -%}
    {%- set pii = (col.meta or {}).get('pii_type') -%}
    {%- if pii -%}
      {%- if pii not in allowed -%}
        {{ exceptions.raise_compiler_error("Model " ~ model.name ~ ": column " ~ col_name ~ " has pii_type '" ~ pii ~ "'; allowed: " ~ allowed | join(', ')) }}
      {%- endif -%}
      {%- if col_name | upper in row_access_keys -%}
        {{ exceptions.raise_compiler_error("Model " ~ model.name ~ ": " ~ col_name ~ " is a row-access key and must not be tagged (a masked column can't be a row access policy argument)") }}
      {%- endif -%}
      {%- if execute -%}
        {%- do run_query("ALTER ICEBERG TABLE " ~ this ~ " MODIFY COLUMN " ~ col_name ~ " SET TAG LAKEHOUSE.GOVERNANCE.PII_TYPE = '" ~ pii ~ "'") -%}
      {%- endif -%}
    {%- endif -%}
  {%- endfor -%}
  select 1
{% endmacro %}
