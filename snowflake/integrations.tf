resource "snowflake_storage_integration_gcs" "landing" {
  name                      = "SI_LANDING"
  enabled                   = true
  storage_allowed_locations = ["gcs://${local.gcp.landing_bucket}/"]
  comment                   = "Read batch files for Snowpipe auto-ingest"
}

resource "snowflake_notification_integration" "landing" {
  name                         = "NI_LANDING"
  enabled                      = true
  notification_provider        = "GCP_PUBSUB"
  gcp_pubsub_subscription_name = local.gcp.landing_notification_subscription
  comment                      = "GCS OBJECT_FINALIZE events for Snowpipe auto-ingest"
}

resource "snowflake_external_volume" "lakehouse" {
  name         = "EV_LAKEHOUSE"
  allow_writes = "true"
  storage_location {
    storage_location_name = "gcs-europe-west4"
    storage_provider      = "GCS"
    storage_base_url      = "gcs://${local.gcp.lakehouse_bucket}/iceberg/"
  }
  comment = "Iceberg data for every layer"
}
