# Service users never get secondary roles: masking policies key on CURRENT_ROLE(), and
# DEFAULT_SECONDARY_ROLES = ('ALL') would make every granted role active.
resource "tls_private_key" "ingest" {
  algorithm = "RSA"
  rsa_bits  = 2048
}

locals {
  ingest_public_key = join("", slice(split("\n", trimspace(tls_private_key.ingest.public_key_pem)), 1, length(split("\n", trimspace(tls_private_key.ingest.public_key_pem))) - 1))
  service_users = merge(
    { for u, r in local.demo_users : u => { role = r, comment = "Demo user for ${r} (Horizon/Spark/DuckDB via PAT)" } },
    { INGEST_SVC = { role = "INGEST", comment = "Pub/Sub -> Snowpipe Streaming bridge" } },
  )
}

resource "snowflake_service_user" "users" {
  for_each                       = local.service_users
  name                           = each.key
  default_role                   = each.value.role
  default_warehouse              = local.query_warehouse
  default_secondary_roles_option = "NONE"
  rsa_public_key                 = each.key == "INGEST_SVC" ? local.ingest_public_key : null
  comment                        = each.value.comment

  lifecycle {
    # `mise run stop` disables INGEST_SVC; Terraform must not silently re-enable it.
    ignore_changes = [disabled]
  }
}

resource "snowflake_user_programmatic_access_token" "demo" {
  for_each         = local.demo_users
  user             = snowflake_service_user.users[each.key].name
  name             = "${each.key}_PAT"
  role_restriction = snowflake_account_role.roles[each.value].name
  days_to_expiry   = var.pat_days_to_expiry
  depends_on       = [snowflake_grant_account_role.users, snowflake_user_authentication_policy_attachment.demo]
}

resource "local_sensitive_file" "pat" {
  for_each        = local.demo_users
  filename        = "${var.secrets_dir}/${lower(each.key)}.pat"
  content         = snowflake_user_programmatic_access_token.demo[each.key].token
  file_permission = "0600"
}

resource "local_sensitive_file" "ingest_key" {
  filename        = "${var.secrets_dir}/ingest_svc.p8"
  content         = tls_private_key.ingest.private_key_pem_pkcs8
  file_permission = "0600"
}
