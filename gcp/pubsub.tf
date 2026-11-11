locals {
  topics = ["orders-events", "clickstream-events", "landing-notifications"]
  subscriptions = {
    "orders-events-bridge"           = "orders-events"         # read by `mise run bridge`
    "clickstream-events-bridge"      = "clickstream-events"    # read by `mise run bridge`
    "landing-notifications-snowpipe" = "landing-notifications" # read by Snowflake (NI_LANDING)
  }
}

resource "google_pubsub_topic" "topics" {
  for_each   = toset(local.topics)
  project    = google_project.data.project_id
  name       = each.value
  depends_on = [google_project_service.apis]
}

resource "google_pubsub_subscription" "subs" {
  for_each                   = local.subscriptions
  project                    = google_project.data.project_id
  name                       = each.key
  topic                      = google_pubsub_topic.topics[each.value].id
  ack_deadline_seconds       = 60
  message_retention_duration = "604800s"
  expiration_policy {
    ttl = "" # never expire while the exercise runs
  }
}
