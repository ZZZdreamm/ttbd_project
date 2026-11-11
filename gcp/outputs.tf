output "data_project_id" {
  value = google_project.data.project_id
}

output "landing_bucket" {
  value = google_storage_bucket.landing.name
}

output "lakehouse_bucket" {
  value = google_storage_bucket.lakehouse.name
}

output "landing_notification_subscription" {
  value = google_pubsub_subscription.subs["landing-notifications-snowpipe"].id
}

output "orders_topic" {
  value = google_pubsub_topic.topics["orders-events"].id
}

output "clickstream_topic" {
  value = google_pubsub_topic.topics["clickstream-events"].id
}

output "orders_subscription" {
  value = google_pubsub_subscription.subs["orders-events-bridge"].id
}

output "clickstream_subscription" {
  value = google_pubsub_subscription.subs["clickstream-events-bridge"].id
}
