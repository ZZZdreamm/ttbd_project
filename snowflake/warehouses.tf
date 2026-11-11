# WH_QUERY (ad-hoc queries, tests, Horizon) belongs to the sf:keygen bootstrap SQL, not to
# Terraform: the provider logs in with it, so it must exist before the first plan and outlive
# `terraform destroy` (`mise run destroy` drops it last). Terraform only grants on it.
# Both warehouses are covered by the account-level RM_LAB (guardrails.tf); Snowflake doesn't allow
# attaching an account-level monitor to individual warehouses.

locals {
  query_warehouse = "WH_QUERY"
}

resource "snowflake_warehouse" "transform" {
  name                = "WH_TRANSFORM"
  warehouse_size      = "XSMALL"
  auto_suspend        = 60
  auto_resume         = "true"
  initially_suspended = true
  comment             = "Dynamic tables and dbt"
}
