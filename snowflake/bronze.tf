locals {
  # Snowflake normalises Iceberg types; use the normalised spelling so plans stay clean.
  STR = "VARCHAR(134217728)"
  TS  = "TIMESTAMP_NTZ(6)"
  TSL = "TIMESTAMP_LTZ(6)"

  # [column, type, PII_TYPE or null]
  bronze = {
    ORDERS_EVENTS = [
      ["EVENT_ID", local.STR, null], ["EVENT_TYPE", local.STR, null], ["EVENT_TS", local.TS, null],
      ["ORDER_ID", local.STR, null], ["CUSTOMER_ID", local.STR, null], ["ITEMS_JSON", local.STR, null],
      ["TOTAL_AMOUNT", "NUMBER(12,2)", null], ["CURRENCY", local.STR, null], ["PAYMENT_METHOD", local.STR, null],
      ["CARD_LAST4", local.STR, "CARD"], ["IP_ADDRESS", local.STR, "IP"], ["SHIPPING_STREET", local.STR, "ADDRESS"],
      ["SHIPPING_CITY", local.STR, null], ["SHIPPING_POSTAL_CODE", local.STR, "ADDRESS"], ["SHIPPING_COUNTRY", local.STR, null],
      ["_INGESTED_AT", local.TSL, null],
    ]
    CLICKSTREAM_EVENTS = [
      ["EVENT_ID", local.STR, null], ["EVENT_TYPE", local.STR, null], ["EVENT_TS", local.TS, null],
      ["SESSION_ID", local.STR, null], ["CUSTOMER_ID", local.STR, null], ["PRODUCT_ID", local.STR, null],
      ["PAGE", local.STR, null], ["IP_ADDRESS", local.STR, "IP"], ["_INGESTED_AT", local.TSL, null],
    ]
    CUSTOMERS_RAW = [
      ["CUSTOMER_ID", local.STR, null], ["FIRST_NAME", local.STR, "NAME"], ["LAST_NAME", local.STR, "NAME"],
      ["EMAIL", local.STR, "EMAIL"], ["PHONE", local.STR, "PHONE"], ["DATE_OF_BIRTH", "DATE", "DOB"],
      ["STREET", local.STR, "ADDRESS"], ["CITY", local.STR, null], ["POSTAL_CODE", local.STR, "ADDRESS"],
      ["COUNTRY", local.STR, null], ["UPDATED_AT", local.TS, null], ["_FILE", local.STR, null], ["_INGESTED_AT", local.TSL, null],
    ]
    PRODUCTS_RAW = [
      ["PRODUCT_ID", local.STR, null], ["NAME", local.STR, null], ["CATEGORY", local.STR, null],
      ["UNIT_PRICE", "NUMBER(10,2)", null], ["UPDATED_AT", local.TS, null], ["_FILE", local.STR, null], ["_INGESTED_AT", local.TSL, null],
    ]
    RETURNS_RAW = [
      ["RETURN_ID", local.STR, null], ["ORDER_ID", local.STR, null], ["PRODUCT_ID", local.STR, null],
      ["QTY", "NUMBER(38,0)", null], ["REASON", local.STR, null], ["RETURNED_AT", local.TS, null],
      ["_FILE", local.STR, null], ["_INGESTED_AT", local.TSL, null],
    ]
  }

  pii_values = ["NAME", "EMAIL", "PHONE", "ADDRESS", "DOB", "IP", "CARD"]
  pii_column_ids = { for v in local.pii_values : v => toset(flatten([
    for t, cols in local.bronze : [for c in cols : "\"LAKEHOUSE\".\"BRONZE\".\"${t}\".\"${c[0]}\"" if c[2] == v]
  ])) }
}

# Column definitions are fixed at creation; this hash forces a (deliberate) replacement
# when they change.
resource "terraform_data" "bronze_schema" {
  for_each = toset(keys(local.bronze))
  input    = sha256(jsonencode(local.bronze[each.value]))
}

resource "snowflake_iceberg_table" "bronze" {
  for_each        = toset(keys(local.bronze))
  database        = snowflake_database.lakehouse.name
  schema          = snowflake_schema.schemas["BRONZE"].name
  name            = each.value
  external_volume = snowflake_external_volume.lakehouse.name
  catalog         = "SNOWFLAKE"
  base_location   = "bronze/${lower(each.value)}"
  change_tracking = "true"

  dynamic "column" {
    for_each = local.bronze[each.value]
    content {
      name = column.value[0]
      type = column.value[1]
    }
  }

  lifecycle {
    # The provider reads tag-based masking back as column.masking_policy and would
    # otherwise recreate the table (dropping its data and tags) on every apply.
    ignore_changes       = [column]
    replace_triggered_by = [terraform_data.bronze_schema[each.key]]
  }
  depends_on = [terraform_data.external_volume_ready]
}

# Tag every PII column (one association per tag value).
resource "snowflake_tag_association" "pii" {
  for_each           = local.pii_column_ids
  tag_id             = snowflake_tag.pii_type.fully_qualified_name
  tag_value          = each.key
  object_type        = "ICEBERG TABLE COLUMN"
  object_identifiers = each.value
  depends_on         = [snowflake_iceberg_table.bronze]

  lifecycle {
    precondition {
      condition     = !anytrue([for id in each.value : can(regex("COUNTRY\"$", id))])
      error_message = "Country columns are row-access keys; Snowflake rejects a masked column as a row access policy argument."
    }
  }
}

# Pipes (owned by PIPELINE_ADMIN) load bronze; the bridge (INGEST) streams into it;
# demo roles read it masked (lesson: bronze is readable but PII is hidden).
resource "snowflake_grant_privileges_to_account_role" "bronze_pipeline" {
  for_each          = snowflake_iceberg_table.bronze
  account_role_name = snowflake_account_role.roles["PIPELINE_ADMIN"].name
  privileges        = ["SELECT", "INSERT"]
  on_schema_object {
    object_type = "ICEBERG TABLE"
    object_name = each.value.fully_qualified_name
  }
}

resource "snowflake_grant_privileges_to_account_role" "bronze_ingest" {
  for_each          = toset(["ORDERS_EVENTS", "CLICKSTREAM_EVENTS"])
  account_role_name = snowflake_account_role.roles["INGEST"].name
  privileges        = ["SELECT", "INSERT"]
  on_schema_object {
    object_type = "ICEBERG TABLE"
    object_name = snowflake_iceberg_table.bronze[each.value].fully_qualified_name
  }
}

resource "snowflake_grant_privileges_to_account_role" "bronze_demo_select" {
  for_each          = { for p in setproduct(local.demo_roles, keys(local.bronze)) : "${p[0]}.${p[1]}" => p }
  account_role_name = snowflake_account_role.roles[each.value[0]].name
  privileges        = ["SELECT"]
  on_schema_object {
    object_type = "ICEBERG TABLE"
    object_name = snowflake_iceberg_table.bronze[each.value[1]].fully_qualified_name
  }
}
