resource "snowflake_database" "lakehouse" {
  name                        = "LAKEHOUSE"
  data_retention_time_in_days = 1
  comment                     = "TBD lakehouse exercise"
}

locals {
  schemas = toset(["BRONZE", "SILVER", "GOLD", "GOVERNANCE", "OPS"])
}

resource "snowflake_schema" "schemas" {
  for_each = local.schemas
  database = snowflake_database.lakehouse.name
  name     = each.value
  # Destroy order: schemas (and the dbt-created Iceberg tables in them) go before the volume.
  depends_on = [snowflake_external_volume.lakehouse]
}
