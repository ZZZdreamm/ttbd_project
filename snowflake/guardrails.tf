# Warehouses: hard stop at the cap (lifetime, not monthly: a trial can cross a month boundary).
resource "snowflake_resource_monitor" "lab" {
  name                      = "RM_LAB"
  credit_quota              = var.credit_cap
  frequency                 = "NEVER"
  start_timestamp           = "IMMEDIATELY"
  notify_triggers           = [50, 75, 90]
  suspend_immediate_trigger = 100
}

resource "snowflake_execute" "account_monitor" {
  execute = "ALTER ACCOUNT SET RESOURCE_MONITOR = ${snowflake_resource_monitor.lab.name}"
  revert  = "ALTER ACCOUNT UNSET RESOURCE_MONITOR"
}

# Serverless spend (Snowpipe, Streaming, External Governance) isn't covered by resource
# monitors: the account budget calls OPS.STOP_ALL() at 95% of the cap.
resource "snowflake_execute" "budget_email_integration" {
  execute = "CREATE NOTIFICATION INTEGRATION IF NOT EXISTS NI_BUDGET_EMAIL TYPE = EMAIL ENABLED = TRUE"
  revert  = "DROP INTEGRATION IF EXISTS NI_BUDGET_EMAIL"
}

resource "snowflake_execute" "budget_grants" {
  execute    = <<-SQL
    EXECUTE IMMEDIATE $$
    BEGIN
      GRANT USAGE ON INTEGRATION NI_BUDGET_EMAIL TO APPLICATION SNOWFLAKE;
      GRANT USAGE ON DATABASE ${snowflake_database.lakehouse.name} TO APPLICATION SNOWFLAKE;
      GRANT USAGE ON SCHEMA ${snowflake_schema.schemas["OPS"].fully_qualified_name} TO APPLICATION SNOWFLAKE;
      GRANT USAGE ON PROCEDURE LAKEHOUSE.OPS.STOP_ALL() TO APPLICATION SNOWFLAKE;
    END;
    $$
  SQL
  revert     = "SELECT 'grants to APPLICATION SNOWFLAKE go away with the objects'"
  depends_on = [snowflake_execute.budget_email_integration, snowflake_procedure_sql.stop_all]
}

resource "snowflake_execute" "budget" {
  execute    = <<-SQL
    EXECUTE IMMEDIATE $$
    BEGIN
      BEGIN
        CALL SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET!ACTIVATE();
      EXCEPTION
        WHEN OTHER THEN NULL; -- BUDGET_ALREADY_ACTIVATED on reruns
      END;
      CALL SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET!SET_SPENDING_LIMIT(${var.credit_cap});
      CALL SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET!SET_EMAIL_NOTIFICATIONS('NI_BUDGET_EMAIL', '${var.notification_email}');
      CALL SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET!REMOVE_CUSTOM_ACTIONS();
      CALL SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET!ADD_CUSTOM_ACTION(SYSTEM$REFERENCE('PROCEDURE', 'LAKEHOUSE.OPS.STOP_ALL()'), ARRAY_CONSTRUCT(), 'ACTUAL', 95);
    END;
    $$
  SQL
  revert     = "CALL SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET!REMOVE_CUSTOM_ACTIONS()"
  depends_on = [snowflake_execute.budget_grants]
}

# Safety net for "forgot `mise run stop`": every night at 23:00 (Europe/Warsaw) stop everything.
# Serverless and tiny; STOP_ALL never suspends this task itself. `mise run start` resumes work.
resource "snowflake_execute" "nightly_stop" {
  execute    = "CREATE OR REPLACE TASK LAKEHOUSE.OPS.NIGHTLY_STOP SCHEDULE = 'USING CRON 0 23 * * * Europe/Warsaw' USER_TASK_MANAGED_INITIAL_WAREHOUSE_SIZE = 'XSMALL' COMMENT = 'Nightly safety stop' AS CALL LAKEHOUSE.OPS.STOP_ALL()"
  revert     = "DROP TASK IF EXISTS LAKEHOUSE.OPS.NIGHTLY_STOP"
  depends_on = [snowflake_procedure_sql.stop_all]
}

resource "snowflake_execute" "nightly_stop_resume" {
  execute    = "ALTER TASK LAKEHOUSE.OPS.NIGHTLY_STOP RESUME"
  revert     = "ALTER TASK IF EXISTS LAKEHOUSE.OPS.NIGHTLY_STOP SUSPEND"
  depends_on = [snowflake_execute.nightly_stop]
}
