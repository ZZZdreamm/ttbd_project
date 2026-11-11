locals {
  prefix     = lower("tbd-${var.semester}-stud${var.team_id}")
  sf_org     = split("-", var.snowflake_account)[0]
  sf_account = split("-", var.snowflake_account)[1]
  gcp        = data.terraform_remote_state.gcp.outputs
}

data "terraform_remote_state" "gcp" {
  backend = "gcs"
  config = {
    bucket = "${local.prefix}-mgmt-tfstate"
    prefix = "gcp"
  }
}

provider "snowflake" {
  organization_name = local.sf_org
  account_name      = local.sf_account
  user              = "TERRAFORM_SVC"
  role              = "ACCOUNTADMIN"
  warehouse         = "WH_QUERY"
  authenticator     = "SNOWFLAKE_JWT"
  private_key       = file(var.snowflake_private_key_path)
  preview_features_enabled = [
    "snowflake_external_volume_resource",
    "snowflake_storage_integration_gcs_resource",
    "snowflake_notification_integration_resource",
    "snowflake_procedure_sql_resource",
    "snowflake_authentication_policy_resource",
    "snowflake_user_authentication_policy_attachment_resource",
    "snowflake_user_programmatic_access_token_resource",
    "snowflake_iceberg_table_resource",
    "snowflake_table_resource",
  ]
}

# Same login, but objects created through this provider are owned by PIPELINE_ADMIN
# (dynamic tables refresh as their owner, which must be exempt from masking).
provider "snowflake" {
  alias             = "pipeline"
  organization_name = local.sf_org
  account_name      = local.sf_account
  user              = "TERRAFORM_SVC"
  role              = "PIPELINE_ADMIN"
  warehouse         = "WH_TRANSFORM"
  authenticator     = "SNOWFLAKE_JWT"
  private_key       = file(var.snowflake_private_key_path)
}

provider "google" {
  project = local.gcp.data_project_id
  region  = "europe-west4"
}
