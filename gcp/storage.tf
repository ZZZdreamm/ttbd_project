# Batch landing zone: generators drop NDJSON files here; GCS events go to Pub/Sub for Snowpipe auto-ingest.
resource "google_storage_bucket" "landing" {
  project                     = google_project.data.project_id
  name                        = "${local.project_id}-landing"
  location                    = upper(var.region)
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true
  depends_on                  = [google_project_service.apis]
}

# Iceberg data for every layer (Snowflake external volume).
resource "google_storage_bucket" "lakehouse" {
  project                     = google_project.data.project_id
  name                        = "${local.project_id}-lakehouse"
  location                    = upper(var.region)
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true
  depends_on                  = [google_project_service.apis]
}

data "google_storage_project_service_account" "gcs" {
  project    = google_project.data.project_id
  depends_on = [google_project_service.apis]
}

resource "google_pubsub_topic_iam_member" "gcs_publisher" {
  project = google_project.data.project_id
  topic   = google_pubsub_topic.topics["landing-notifications"].name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${data.google_storage_project_service_account.gcs.email_address}"
}

resource "google_storage_notification" "landing" {
  bucket         = google_storage_bucket.landing.name
  topic          = google_pubsub_topic.topics["landing-notifications"].id
  event_types    = ["OBJECT_FINALIZE"]
  payload_format = "JSON_API_V1"
  depends_on     = [google_pubsub_topic_iam_member.gcs_publisher]
}
