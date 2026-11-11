mock_provider "snowflake" {
  override_during = plan
  mock_resource "snowflake_external_volume" {
    defaults = {
      describe_output = [{ active = "", allow_writes = "true", comment = "", storage_locations = [{ name = "gcs-europe-west4", storage_provider = "GCS", storage_base_url = "gcs://x/iceberg/", storage_allowed_locations = [], encryption_type = "NONE", azure_storage_location = [], s3_storage_location = [], s3_compat_storage_location = [], gcs_storage_location = [{ encryption_kms_key_id = "", storage_gcp_service_account = "ev-sa@sf.iam.gserviceaccount.com" }] }] }]
    }
  }
  mock_resource "snowflake_storage_integration_gcs" {
    defaults = {
      describe_output = [{ service_account = "si-sa@sf.iam.gserviceaccount.com", allowed_locations = [], blocked_locations = [], comment = "", enabled = true, id = "", provider = "GCS", use_privatelink_endpoint = false }]
    }
  }
  mock_resource "snowflake_notification_integration" {
    defaults = {
      gcp_pubsub_service_account = "ni-sa@sf.iam.gserviceaccount.com"
    }
  }
}
mock_provider "snowflake" {
  alias = "pipeline"
}
mock_provider "google" {}
mock_provider "tls" {}
mock_provider "local" {}

override_data {
  target = data.terraform_remote_state.gcp
  values = {
    outputs = {
      data_project_id                   = "tbd-2026z-stud07-data"
      landing_bucket                    = "tbd-2026z-stud07-data-landing"
      lakehouse_bucket                  = "tbd-2026z-stud07-data-lakehouse"
      landing_notification_subscription = "projects/tbd-2026z-stud07-data/subscriptions/landing-notifications-snowpipe"
    }
  }
}

variables {
  semester                   = "2026z"
  team_id                    = "07"
  snowflake_account          = "MYORG-TBD07"
  notification_email         = "a@b.pl"
  snowflake_private_key_path = "tests/no-such-key.p8" # mock providers never read it
}

run "warehouses_xsmall_autosuspend_monitored" {
  command = plan
  assert {
    condition = (snowflake_warehouse.transform.warehouse_size == "XSMALL" && snowflake_warehouse.transform.auto_suspend == 60 &&
    snowflake_warehouse.transform.initially_suspended == true && snowflake_warehouse.transform.resource_monitor == null)
    error_message = "WH_TRANSFORM must be XSMALL, auto_suspend 60, initially suspended (covered by the account-level RM_LAB)"
  }
  assert {
    condition     = snowflake_warehouse.transform.name == "WH_TRANSFORM" && local.query_warehouse == "WH_QUERY"
    error_message = "warehouse names"
  }
}

run "resource_monitor_caps_at_12_credits" {
  command = plan
  assert {
    condition     = snowflake_resource_monitor.lab.name == "RM_LAB" && snowflake_resource_monitor.lab.credit_quota == 12
    error_message = "RM_LAB with 12 credits"
  }
  assert {
    condition     = snowflake_resource_monitor.lab.notify_triggers == toset([50, 75, 90]) && snowflake_resource_monitor.lab.suspend_immediate_trigger == 100
    error_message = "notify 50/75/90, suspend immediately at 100"
  }
  assert {
    condition     = strcontains(snowflake_execute.account_monitor.execute, "ALTER ACCOUNT SET RESOURCE_MONITOR = RM_LAB")
    error_message = "RM_LAB must also be the account-level monitor"
  }
}

run "budget_limit_and_stop_action" {
  command = plan
  assert {
    condition     = strcontains(snowflake_execute.budget.execute, "SET_SPENDING_LIMIT(12)")
    error_message = "account budget spending limit 12 credits"
  }
  assert {
    condition     = strcontains(snowflake_execute.budget.execute, "ADD_CUSTOM_ACTION(SYSTEM$REFERENCE('PROCEDURE', 'LAKEHOUSE.OPS.STOP_ALL()'), ARRAY_CONSTRUCT(), 'ACTUAL', 95)")
    error_message = "budget custom action must call OPS.STOP_ALL at 95% actual spend"
  }
  assert {
    condition     = strcontains(snowflake_execute.budget.execute, "'a@b.pl'")
    error_message = "budget emails go to notification_email"
  }
}

run "lakehouse_storage_wiring" {
  command = plan
  assert {
    condition = (
      snowflake_external_volume.lakehouse.name == "EV_LAKEHOUSE" &&
      snowflake_external_volume.lakehouse.allow_writes == "true" &&
      snowflake_external_volume.lakehouse.storage_location[0].storage_base_url == "gcs://tbd-2026z-stud07-data-lakehouse/iceberg/" &&
      snowflake_external_volume.lakehouse.storage_location[0].storage_provider == "GCS"
    )
    error_message = "EV_LAKEHOUSE on gcs://<lakehouse>/iceberg/ with writes allowed"
  }
  assert {
    condition     = snowflake_storage_integration_gcs.landing.name == "SI_LANDING" && snowflake_storage_integration_gcs.landing.storage_allowed_locations == toset(["gcs://tbd-2026z-stud07-data-landing/"])
    error_message = "SI_LANDING limited to the landing bucket"
  }
  assert {
    condition     = snowflake_notification_integration.landing.name == "NI_LANDING" && snowflake_notification_integration.landing.gcp_pubsub_subscription_name == "projects/tbd-2026z-stud07-data/subscriptions/landing-notifications-snowpipe"
    error_message = "NI_LANDING reads landing-notifications-snowpipe"
  }
}

run "gcp_iam_for_snowflake_service_accounts" {
  command = plan
  assert {
    condition = (google_storage_bucket_iam_member.si_landing_viewer.bucket == "tbd-2026z-stud07-data-landing" &&
      google_storage_bucket_iam_member.si_landing_viewer.role == "roles/storage.objectViewer" &&
    google_storage_bucket_iam_member.si_landing_viewer.member == "serviceAccount:si-sa@sf.iam.gserviceaccount.com")
    error_message = "storage integration SA reads the landing bucket"
  }
  assert {
    condition = (toset(keys(google_storage_bucket_iam_member.ev_lakehouse)) == toset(["roles/storage.objectUser", "roles/storage.legacyBucketReader"]) &&
      alltrue([for m in google_storage_bucket_iam_member.ev_lakehouse :
    m.bucket == "tbd-2026z-stud07-data-lakehouse" && m.member == "serviceAccount:ev-sa@sf.iam.gserviceaccount.com"]))
    error_message = "external volume SA gets objectUser + legacyBucketReader on the lakehouse bucket"
  }
  assert {
    condition = (google_pubsub_subscription_iam_member.ni_subscriber.role == "roles/pubsub.subscriber" &&
      google_pubsub_subscription_iam_member.ni_subscriber.member == "serviceAccount:ni-sa@sf.iam.gserviceaccount.com" &&
    google_project_iam_member.ni_monitoring.role == "roles/monitoring.viewer")
    error_message = "notification SA subscribes and can view monitoring"
  }
}

run "roles_users_pats" {
  command = plan
  assert {
    condition     = toset([for r in snowflake_account_role.roles : r.name]) == toset(["PIPELINE_ADMIN", "INGEST", "ANALYST", "SUPPORT", "PII_ADMIN"])
    error_message = "account roles"
  }
  assert {
    condition = alltrue([for u, r in local.demo_users :
    snowflake_user_programmatic_access_token.demo[u].role_restriction == r])
    error_message = "each demo PAT is restricted to its role"
  }
  assert {
    condition = alltrue([for u in concat(keys(local.demo_users), ["INGEST_SVC"]) :
    snowflake_service_user.users[u].default_secondary_roles_option == "NONE"])
    error_message = "service users must not get secondary roles (would bypass CURRENT_ROLE-based masking)"
  }
}

run "nightly_safety_stop" {
  command = plan
  assert {
    condition     = strcontains(snowflake_execute.nightly_stop.execute, "SCHEDULE = 'USING CRON 0 23 * * * Europe/Warsaw'") && strcontains(snowflake_execute.nightly_stop.execute, "CALL LAKEHOUSE.OPS.STOP_ALL()")
    error_message = "a nightly task must stop everything at 23:00 Europe/Warsaw"
  }
  assert {
    condition     = strcontains(snowflake_procedure_sql.stop_all.procedure_definition, "NIGHTLY_STOP")
    error_message = "STOP_ALL must not suspend the nightly stop task itself"
  }
}
