locals {
  si_service_account = snowflake_storage_integration_gcs.landing.describe_output[0].service_account
  ev_service_account = snowflake_external_volume.lakehouse.describe_output[0].storage_locations[0].gcs_storage_location[0].storage_gcp_service_account
  ni_service_account = snowflake_notification_integration.landing.gcp_pubsub_service_account
}

resource "google_storage_bucket_iam_member" "si_landing_viewer" {
  bucket = local.gcp.landing_bucket
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${local.si_service_account}"
}

resource "google_storage_bucket_iam_member" "si_landing_bucket_reader" {
  bucket = local.gcp.landing_bucket
  role   = "roles/storage.legacyBucketReader"
  member = "serviceAccount:${local.si_service_account}"
}

# Snowflake needs storage.buckets.get + objects create/delete/get/list on the Iceberg bucket.
resource "google_storage_bucket_iam_member" "ev_lakehouse" {
  for_each = toset(["roles/storage.objectUser", "roles/storage.legacyBucketReader"])
  bucket   = local.gcp.lakehouse_bucket
  role     = each.value
  member   = "serviceAccount:${local.ev_service_account}"
}

# A brand-new volume rejects CREATE ICEBERG TABLE (091369 "Query needs to be retried to setup
# external volume") until the grants above have propagated. Wait until Snowflake can write.
resource "terraform_data" "external_volume_ready" {
  input = snowflake_external_volume.lakehouse.name
  provisioner "local-exec" {
    interpreter = ["bash", "-c"]
    command     = <<-EOT
      for i in $(seq 1 30); do
        out=$(snow sql -q "SELECT SYSTEM\$VERIFY_EXTERNAL_VOLUME('${self.input}')" --format json 2>&1) || true
        echo "$out" | grep -q 'success[^,]*true' && { echo "external volume ${self.input} ready"; exit 0; }
        sleep 10
      done
      echo "$out"; echo "external volume ${self.input} still not usable after 5 minutes" >&2; exit 1
    EOT
  }
  depends_on = [google_storage_bucket_iam_member.ev_lakehouse]
}

resource "google_pubsub_subscription_iam_member" "ni_subscriber" {
  project      = local.gcp.data_project_id
  subscription = local.gcp.landing_notification_subscription
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${local.ni_service_account}"
}

resource "google_project_iam_member" "ni_monitoring" {
  project = local.gcp.data_project_id
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:${local.ni_service_account}"
}
