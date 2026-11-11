-- Resume pipelines after `mise run stop`. Refuses once RM_LAB has used the whole cap.
DECLARE
  log VARCHAR DEFAULT '';
  stmts ARRAY DEFAULT ARRAY_CONSTRUCT();
  used FLOAT DEFAULT 0;
  quota FLOAT DEFAULT 1;
  rs RESULTSET;
BEGIN
  SHOW RESOURCE MONITORS LIKE 'RM_LAB';
  SELECT COALESCE(MAX("used_credits"::FLOAT), 0), COALESCE(MAX("credit_quota"::FLOAT), 1)
    INTO :used, :quota FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
  IF (used >= quota) THEN
    RETURN 'refused: RM_LAB has used ' || used || ' of ' || quota || ' credits';
  END IF;

  SHOW PIPES IN DATABASE LAKEHOUSE;
  rs := (SELECT 'ALTER PIPE IF EXISTS "' || "database_name" || '"."' || "schema_name" || '"."' || "name" || '" SET PIPE_EXECUTION_PAUSED = FALSE' AS s
         FROM TABLE(RESULT_SCAN(LAST_QUERY_ID())));
  FOR r IN rs DO stmts := ARRAY_APPEND(stmts, r.s); END FOR;

  SHOW DYNAMIC TABLES IN DATABASE LAKEHOUSE;
  rs := (SELECT 'ALTER DYNAMIC TABLE IF EXISTS "' || "database_name" || '"."' || "schema_name" || '"."' || "name" || '" RESUME' AS s
         FROM TABLE(RESULT_SCAN(LAST_QUERY_ID())) WHERE "scheduling_state" = 'SUSPENDED');
  FOR r IN rs DO stmts := ARRAY_APPEND(stmts, r.s); END FOR;

  SHOW TASKS IN DATABASE LAKEHOUSE;
  rs := (SELECT 'ALTER TASK IF EXISTS "' || "database_name" || '"."' || "schema_name" || '"."' || "name" || '" RESUME' AS s
         FROM TABLE(RESULT_SCAN(LAST_QUERY_ID())) WHERE "state" = 'suspended');
  FOR r IN rs DO stmts := ARRAY_APPEND(stmts, r.s); END FOR;

  stmts := ARRAY_APPEND(stmts, 'ALTER USER IF EXISTS INGEST_SVC SET DISABLED = FALSE');

  FOR i IN 0 TO ARRAY_SIZE(stmts) - 1 DO
    LET s VARCHAR := stmts[i];
    BEGIN
      EXECUTE IMMEDIATE :s;
      log := log || 'ok: ' || s || '\n';
    EXCEPTION
      WHEN OTHER THEN
        log := log || 'skipped: ' || s || ' (' || SQLERRM || ')\n';
    END;
  END FOR;
  RETURN log;
END;
