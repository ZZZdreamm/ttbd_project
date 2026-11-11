locals {
  pii_tag_fqn = "LAKEHOUSE.GOVERNANCE.PII_TYPE"
  # Roles that see raw values. PIPELINE_ADMIN must be here: dynamic tables and dbt models are
  # built as their owner role, and would otherwise store already-masked values.
  raw_roles      = ["PII_ADMIN", "PIPELINE_ADMIN"]
  all_rows_roles = ["PII_ADMIN", "PIPELINE_ADMIN", "ANALYST", "ACCOUNTADMIN"]
  sql_list       = { for k, v in { raw = local.raw_roles, all_rows = local.all_rows_roles } : k => join(", ", [for r in v : "'${r}'"]) }

  support_countries = { SUPPORT_USER = ["PL", "NL"] }
}

resource "snowflake_masking_policy" "pii_string" {
  database = snowflake_database.lakehouse.name
  schema   = snowflake_schema.schemas["GOVERNANCE"].name
  name     = "MP_PII_STRING"
  argument {
    name = "VAL"
    type = "VARCHAR"
  }
  return_data_type = "VARCHAR"
  body             = templatefile("${path.module}/sql/mp_pii_string.sql", { raw_roles = local.sql_list.raw, tag = local.pii_tag_fqn })
  comment          = "PII_TYPE-driven masking for text columns"
  depends_on       = [snowflake_tag.pii_type]
}

resource "snowflake_masking_policy" "pii_date" {
  database = snowflake_database.lakehouse.name
  schema   = snowflake_schema.schemas["GOVERNANCE"].name
  name     = "MP_PII_DATE"
  argument {
    name = "VAL"
    type = "DATE"
  }
  return_data_type = "DATE"
  body             = templatefile("${path.module}/sql/mp_pii_date.sql", { raw_roles = local.sql_list.raw })
  comment          = "PII_TYPE-driven masking for date columns (DOB)"
}

resource "snowflake_execute" "tag_masking" {
  for_each = {
    string = snowflake_masking_policy.pii_string.fully_qualified_name
    date   = snowflake_masking_policy.pii_date.fully_qualified_name
  }
  execute = "ALTER TAG ${snowflake_tag.pii_type.fully_qualified_name} SET MASKING POLICY ${each.value}"
  revert  = "ALTER TAG ${snowflake_tag.pii_type.fully_qualified_name} UNSET MASKING POLICY ${each.value}"
}

# One tag, two policies (a tag can carry one masking policy per data type). Propagation
# carries the tag (and so the masking) from bronze columns to dynamic tables and dbt models.
# The tag is created first: MP_PII_STRING references it, and Snowflake checks that at CREATE.
resource "snowflake_tag" "pii_type" {
  database               = snowflake_database.lakehouse.name
  schema                 = snowflake_schema.schemas["GOVERNANCE"].name
  name                   = "PII_TYPE"
  ordered_allowed_values = ["NAME", "EMAIL", "PHONE", "ADDRESS", "DOB", "IP", "CARD"]
  propagate              = "ON_DEPENDENCY_AND_DATA_MOVEMENT"
  comment                = "What kind of personal data a column holds"

  lifecycle {
    # Bound by snowflake_execute.tag_masking (policies must be created after the tag).
    ignore_changes = [masking_policies]
  }
}

resource "snowflake_table" "support_country_map" {
  database = snowflake_database.lakehouse.name
  schema   = snowflake_schema.schemas["GOVERNANCE"].name
  name     = "SUPPORT_COUNTRY_MAP"
  column {
    name = "USER_NAME"
    type = "VARCHAR(256)"
  }
  column {
    name = "COUNTRY"
    type = "VARCHAR(2)"
  }
  comment = "Which countries each SUPPORT user may see (row access attribute)"
}

resource "snowflake_execute" "support_country_rows" {
  execute = "INSERT INTO ${snowflake_table.support_country_map.fully_qualified_name} (USER_NAME, COUNTRY) SELECT * FROM VALUES ${join(", ", flatten([for u, cs in local.support_countries : [for c in cs : "('${u}', '${c}')"]]))}"
  revert  = "DELETE FROM ${snowflake_table.support_country_map.fully_qualified_name}"
}

resource "snowflake_row_access_policy" "support_country" {
  database = snowflake_database.lakehouse.name
  schema   = snowflake_schema.schemas["GOVERNANCE"].name
  name     = "RAP_SUPPORT_COUNTRY"
  argument {
    name = "COUNTRY"
    type = "VARCHAR"
  }
  body = templatefile("${path.module}/sql/rap_support_country.sql", {
    all_rows_roles = local.sql_list.all_rows
    map_table      = "LAKEHOUSE.GOVERNANCE.SUPPORT_COUNTRY_MAP"
  })
  comment    = "SUPPORT sees only its mapped countries; attached by dbt to SILVER.CUSTOMERS_CURRENT"
  depends_on = [snowflake_table.support_country_map]
}

resource "snowflake_grant_privileges_to_account_role" "pipeline_apply_rap" {
  account_role_name = snowflake_account_role.roles["PIPELINE_ADMIN"].name
  privileges        = ["APPLY"]
  on_schema_object {
    object_type = "ROW ACCESS POLICY"
    object_name = snowflake_row_access_policy.support_country.fully_qualified_name
  }
}
