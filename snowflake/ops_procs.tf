resource "snowflake_procedure_sql" "stop_all" {
  database             = snowflake_database.lakehouse.name
  schema               = snowflake_schema.schemas["OPS"].name
  name                 = "STOP_ALL"
  return_type          = "VARCHAR"
  execute_as           = "OWNER"
  procedure_definition = file("${path.module}/sql/stop_all.sql")
  comment              = "Suspend everything that can spend credits (mise run stop; budget action)"
}

resource "snowflake_procedure_sql" "start_all" {
  database             = snowflake_database.lakehouse.name
  schema               = snowflake_schema.schemas["OPS"].name
  name                 = "START_ALL"
  return_type          = "VARCHAR"
  execute_as           = "OWNER"
  procedure_definition = file("${path.module}/sql/start_all.sql")
  comment              = "Resume pipelines unless RM_LAB is exhausted (mise run start)"
}
