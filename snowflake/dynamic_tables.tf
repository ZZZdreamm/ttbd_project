# Streaming silver/gold: dynamic Iceberg tables over the Snowpipe Streaming bronze tables.
# (DCM can't define dynamic *Iceberg* tables yet, so Terraform owns them.)
# PII columns get their PII_TYPE tag automatically via tag propagation from bronze.
locals {
  dt_common = "TARGET_LAG = '${var.dt_target_lag}' WAREHOUSE = WH_TRANSFORM EXTERNAL_VOLUME = 'EV_LAKEHOUSE' CATALOG = 'SNOWFLAKE'"

  dynamic_tables = {
    "SILVER.ORDERS_LATEST" = <<-SQL
      -- one row per order: latest status by event time (not arrival); duplicates removed by event_id
      SELECT order_id, customer_id, event_type AS status, event_ts AS status_ts, items_json, total_amount,
             currency, payment_method, card_last4, ip_address,
             shipping_street, shipping_city, shipping_postal_code, shipping_country
      FROM (
        SELECT * FROM LAKEHOUSE.BRONZE.ORDERS_EVENTS
        QUALIFY ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY _ingested_at) = 1
      )
      QUALIFY ROW_NUMBER() OVER (
        PARTITION BY order_id
        ORDER BY event_ts DESC,
                 CASE event_type WHEN 'delivered' THEN 4 WHEN 'cancelled' THEN 4 WHEN 'shipped' THEN 3
                                 WHEN 'paid' THEN 2 ELSE 1 END DESC
      ) = 1
    SQL
    "SILVER.CLICKSTREAM"   = <<-SQL
      SELECT event_id, event_type, event_ts, session_id, customer_id, product_id, page, ip_address
      FROM LAKEHOUSE.BRONZE.CLICKSTREAM_EVENTS
      QUALIFY ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY _ingested_at) = 1
    SQL
  }

  dt_gold_sql = <<-SQL
      -- near-real-time KPI; no PII (DuckDB reads this without masking)
      SELECT shipping_country, status, COUNT(*) AS order_count, SUM(total_amount)::NUMBER(14, 2) AS revenue
      FROM LAKEHOUSE.SILVER.ORDERS_LATEST
      GROUP BY shipping_country, status
  SQL
}

resource "snowflake_execute" "dynamic_table" {
  for_each = local.dynamic_tables
  provider = snowflake.pipeline

  execute = "CREATE OR REPLACE DYNAMIC ICEBERG TABLE LAKEHOUSE.${each.key} ${local.dt_common} BASE_LOCATION = '${lower(replace(each.key, ".", "/"))}' AS ${each.value}"
  revert  = "DROP DYNAMIC TABLE IF EXISTS LAKEHOUSE.${each.key}"

  depends_on = [
    snowflake_iceberg_table.bronze,
    snowflake_tag_association.pii,
    snowflake_grant_privileges_to_account_role.bronze_pipeline,
    snowflake_grant_privileges_to_account_role.pipeline_schemas,
    snowflake_grant_privileges_to_account_role.pipeline_warehouses,
    snowflake_grant_privileges_to_account_role.external_volume,
    snowflake_grant_account_role.to_terraform_svc,
  ]
}

# Gold reads silver, so it is created after it.
resource "snowflake_execute" "dynamic_table_gold" {
  provider   = snowflake.pipeline
  execute    = "CREATE OR REPLACE DYNAMIC ICEBERG TABLE LAKEHOUSE.GOLD.ORDERS_BY_COUNTRY_STATUS_RT ${local.dt_common} BASE_LOCATION = 'gold/orders_by_country_status_rt' AS ${local.dt_gold_sql}"
  revert     = "DROP DYNAMIC TABLE IF EXISTS LAKEHOUSE.GOLD.ORDERS_BY_COUNTRY_STATUS_RT"
  depends_on = [snowflake_execute.dynamic_table]
}
