-- Batch transformations: run the dbt project (deployed by `mise run dbt:deploy`) every 15 minutes
-- on WH_TRANSFORM, so the resource monitor caps it. `mise run stop` suspends it.
DEFINE TASK LAKEHOUSE.OPS.RUN_DBT
  WAREHOUSE = WH_TRANSFORM
  SCHEDULE = '15 MINUTE'
  COMMENT = 'dbt build of the batch silver/gold models'
  STARTED
AS EXECUTE DBT PROJECT LAKEHOUSE.OPS.LAKEHOUSE_DBT ARGS = 'build --exclude test_type:unit';
