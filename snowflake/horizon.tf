# Demo users authenticate to Horizon (Spark/DuckDB) with PATs; without this policy a
# service user's PAT would also require a network policy.
resource "snowflake_authentication_policy" "pat_no_netpol" {
  database = snowflake_database.lakehouse.name
  schema   = snowflake_schema.schemas["GOVERNANCE"].name
  name     = "AP_PAT_NO_NETPOL"
  pat_policy {
    network_policy_evaluation = "ENFORCED_NOT_REQUIRED"
  }
  comment = "Lab only: allow PATs from laptops without a network policy"
}

resource "snowflake_user_authentication_policy_attachment" "demo" {
  for_each                   = local.demo_users
  user_name                  = snowflake_service_user.users[each.key].name
  authentication_policy_name = snowflake_authentication_policy.pat_no_netpol.fully_qualified_name
}
