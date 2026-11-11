-- Suspend every object in LAKEHOUSE that can spend credits. Safe to call repeatedly and
-- when objects don't exist yet. Used by `mise run stop` and the budget custom action.
DECLARE
  log VARCHAR DEFAULT '';
  stmts ARRAY DEFAULT ARRAY_CONSTRUCT();
  rs RESULTSET;
BEGIN
  SHOW TASKS IN DATABASE LAKEHOUSE;
  rs := (SELECT 'ALTER TASK IF EXISTS "' || "database_name" || '"."' || "schema_name" || '"."' || "name" || '" SUSPEND' AS s
         FROM TABLE(RESULT_SCAN(LAST_QUERY_ID())) WHERE "state" = 'started' AND "name" <> 'NIGHTLY_STOP');
  FOR r IN rs DO stmts := ARRAY_APPEND(stmts, r.s); END FOR;

  SHOW DYNAMIC TABLES IN DATABASE LAKEHOUSE;
  rs := (SELECT 'ALTER DYNAMIC TABLE IF EXISTS "' || "database_name" || '"."' || "schema_name" || '"."' || "name" || '" SUSPEND' AS s
         FROM TABLE(RESULT_SCAN(LAST_QUERY_ID())) WHERE "scheduling_state" <> 'SUSPENDED');
  FOR r IN rs DO stmts := ARRAY_APPEND(stmts, r.s); END FOR;

  SHOW PIPES IN DATABASE LAKEHOUSE;
  rs := (SELECT 'ALTER PIPE IF EXISTS "' || "database_name" || '"."' || "schema_name" || '"."' || "name" || '" SET PIPE_EXECUTION_PAUSED = TRUE' AS s
         FROM TABLE(RESULT_SCAN(LAST_QUERY_ID())));
  FOR r IN rs DO stmts := ARRAY_APPEND(stmts, r.s); END FOR;

  stmts := ARRAY_CAT(stmts, ARRAY_CONSTRUCT(
    'ALTER USER IF EXISTS INGEST_SVC SET DISABLED = TRUE',
    'ALTER WAREHOUSE IF EXISTS WH_TRANSFORM SUSPEND',
    'ALTER WAREHOUSE IF EXISTS WH_QUERY SUSPEND'));

  FOR i IN 0 TO ARRAY_SIZE(stmts) - 1 DO
    LET s VARCHAR := stmts[i];
    BEGIN
      EXECUTE IMMEDIATE :s;
      log := log || 'ok: ' || s || '\n';
    EXCEPTION
      WHEN OTHER THEN
        -- e.g. warehouse already suspended
        log := log || 'skipped: ' || s || ' (' || SQLERRM || ')\n';
    END;
  END FOR;
  RETURN log;
END;
