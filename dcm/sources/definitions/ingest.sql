-- Batch ingestion: GCS landing bucket -> Snowpipe auto-ingest -> bronze Iceberg tables.
-- The bronze tables themselves are created by Terraform (snowflake/bronze.tf).

DEFINE FILE FORMAT LAKEHOUSE.BRONZE.NDJSON
  TYPE = JSON
  STRIP_OUTER_ARRAY = FALSE;

DEFINE STAGE LAKEHOUSE.BRONZE.LANDING_STAGE
  URL = 'gcs://{{ landing_bucket }}/'
  STORAGE_INTEGRATION = SI_LANDING
  FILE_FORMAT = LAKEHOUSE.BRONZE.NDJSON;

{% for entity, table in [('customers', 'CUSTOMERS_RAW'), ('products', 'PRODUCTS_RAW'), ('returns', 'RETURNS_RAW')] %}
DEFINE PIPE LAKEHOUSE.BRONZE.PIPE_{{ entity | upper }}
  AUTO_INGEST = TRUE
  INTEGRATION = 'NI_LANDING'
  COMMENT = 'Auto-ingest gs://{{ landing_bucket }}/{{ entity }}/ into BRONZE.{{ table }}'
AS COPY INTO LAKEHOUSE.BRONZE.{{ table }}
  FROM @LAKEHOUSE.BRONZE.LANDING_STAGE/{{ entity }}/
  FILE_FORMAT = (FORMAT_NAME = 'LAKEHOUSE.BRONZE.NDJSON')
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
  INCLUDE_METADATA = (_FILE = METADATA$FILENAME, _INGESTED_AT = METADATA$START_SCAN_TIME);
{% endfor %}
