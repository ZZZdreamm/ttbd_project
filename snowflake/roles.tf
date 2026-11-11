locals {
  roles = ["PIPELINE_ADMIN", "INGEST", "ANALYST", "SUPPORT", "PII_ADMIN"]
  demo_users = {
    ANALYST_USER   = "ANALYST"
    SUPPORT_USER   = "SUPPORT"
    PII_ADMIN_USER = "PII_ADMIN"
  }
  demo_roles   = toset(values(local.demo_users))
  data_schemas = toset(["BRONZE", "SILVER", "GOLD"])
}

resource "snowflake_account_role" "roles" {
  for_each = toset(local.roles)
  name     = each.value
}

# Live tests run as TERRAFORM_SVC with USE ROLE <role>.
resource "snowflake_grant_account_role" "to_terraform_svc" {
  for_each  = toset(local.roles)
  role_name = snowflake_account_role.roles[each.value].name
  user_name = "TERRAFORM_SVC"
}

resource "snowflake_grant_account_role" "users" {
  for_each  = merge(local.demo_users, { INGEST_SVC = "INGEST" })
  role_name = snowflake_account_role.roles[each.value].name
  user_name = snowflake_service_user.users[each.key].name
}

# --- PIPELINE_ADMIN: owns pipeline objects (DCM, dbt, dynamic tables) ---
resource "snowflake_grant_privileges_to_account_role" "pipeline_db" {
  account_role_name = snowflake_account_role.roles["PIPELINE_ADMIN"].name
  privileges        = ["USAGE", "MONITOR"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.lakehouse.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "pipeline_schemas" {
  for_each          = local.schemas
  account_role_name = snowflake_account_role.roles["PIPELINE_ADMIN"].name
  all_privileges    = true
  on_schema {
    schema_name = snowflake_schema.schemas[each.value].fully_qualified_name
  }
}

resource "snowflake_grant_privileges_to_account_role" "pipeline_account" {
  account_role_name = snowflake_account_role.roles["PIPELINE_ADMIN"].name
  privileges        = ["EXECUTE TASK", "APPLY TAG", "APPLY ROW ACCESS POLICY"]
  on_account        = true
}

resource "snowflake_grant_privileges_to_account_role" "pipeline_warehouses" {
  for_each          = { transform = snowflake_warehouse.transform.name, query = local.query_warehouse }
  account_role_name = snowflake_account_role.roles["PIPELINE_ADMIN"].name
  privileges        = ["USAGE", "OPERATE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = each.value
  }
}

resource "snowflake_grant_privileges_to_account_role" "pipeline_integrations" {
  for_each = {
    si = snowflake_storage_integration_gcs.landing.name
    ni = snowflake_notification_integration.landing.name
  }
  account_role_name = snowflake_account_role.roles["PIPELINE_ADMIN"].name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "INTEGRATION"
    object_name = each.value
  }
}

# Every role that owns or reads Iceberg tables needs USAGE on the external volume
# (Horizon vended credentials fail otherwise).
resource "snowflake_grant_privileges_to_account_role" "external_volume" {
  for_each          = toset(["PIPELINE_ADMIN", "INGEST", "ANALYST", "SUPPORT", "PII_ADMIN"])
  account_role_name = snowflake_account_role.roles[each.value].name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "EXTERNAL VOLUME"
    object_name = snowflake_external_volume.lakehouse.name
  }
}

# --- INGEST: the bridge (table/pipe grants are added with those objects) ---
resource "snowflake_grant_privileges_to_account_role" "ingest_db" {
  account_role_name = snowflake_account_role.roles["INGEST"].name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.lakehouse.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "ingest_bronze" {
  account_role_name = snowflake_account_role.roles["INGEST"].name
  privileges        = ["USAGE"]
  on_schema {
    schema_name = snowflake_schema.schemas["BRONZE"].fully_qualified_name
  }
}

# --- Demo roles: read silver/gold (and bronze, masked, for the lesson) ---
resource "snowflake_grant_privileges_to_account_role" "demo_db" {
  for_each          = local.demo_roles
  account_role_name = snowflake_account_role.roles[each.value].name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.lakehouse.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "demo_schemas" {
  for_each          = { for p in setproduct(local.demo_roles, local.data_schemas) : "${p[0]}.${p[1]}" => p }
  account_role_name = snowflake_account_role.roles[each.value[0]].name
  privileges        = ["USAGE"]
  on_schema {
    schema_name = snowflake_schema.schemas[each.value[1]].fully_qualified_name
  }
}

resource "snowflake_grant_privileges_to_account_role" "demo_future_select" {
  for_each = { for p in setproduct(local.demo_roles, local.data_schemas, ["ICEBERG TABLES", "DYNAMIC TABLES", "TABLES", "VIEWS"]) :
  "${p[0]}.${p[1]}.${p[2]}" => p }
  account_role_name = snowflake_account_role.roles[each.value[0]].name
  privileges        = ["SELECT"]
  on_schema_object {
    future {
      object_type_plural = each.value[2]
      in_schema          = snowflake_schema.schemas[each.value[1]].fully_qualified_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "demo_warehouse" {
  for_each          = local.demo_roles
  account_role_name = snowflake_account_role.roles[each.value].name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = local.query_warehouse
  }
}

# Standard hierarchy: custom roles roll up to SYSADMIN (and so to ACCOUNTADMIN). Needed so the
# ACCOUNTADMIN-owned OPS.STOP_ALL()/START_ALL() can suspend PIPELINE_ADMIN-owned objects.
# Masking keys on CURRENT_ROLE(), so inheriting PIPELINE_ADMIN doesn't unmask anything.
resource "snowflake_grant_account_role" "pipeline_to_sysadmin" {
  role_name        = snowflake_account_role.roles["PIPELINE_ADMIN"].name
  parent_role_name = "SYSADMIN"
}
