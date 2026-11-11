mock_provider "google" {
  mock_data "google_storage_project_service_account" {
    defaults = {
      email_address = "service-123@gs-project-accounts.iam.gserviceaccount.com"
    }
  }
}

variables {
  semester           = "2026Z"
  team_id            = "07"
  billing_account    = "01ABCD-23EF45-6789AB"
  notification_email = "a@b.pl"
}

run "data_project_named_and_billed" {
  command = plan
  assert {
    condition     = google_project.data.project_id == "tbd-2026z-stud07-data" && google_project.data.billing_account == "01ABCD-23EF45-6789AB"
    error_message = "data project id/billing"
  }
}

run "buckets_private_eu_destroyable" {
  command = plan
  assert {
    condition     = google_storage_bucket.landing.name == "tbd-2026z-stud07-data-landing" && google_storage_bucket.lakehouse.name == "tbd-2026z-stud07-data-lakehouse"
    error_message = "bucket names"
  }
  assert {
    condition = alltrue([for b in [google_storage_bucket.landing, google_storage_bucket.lakehouse] :
    b.location == "EUROPE-WEST4" && b.uniform_bucket_level_access && b.force_destroy && b.public_access_prevention == "enforced"])
    error_message = "buckets must be EUROPE-WEST4, UBLA, force_destroy, public access prevention enforced"
  }
}

run "landing_notifications_to_pubsub" {
  command = plan
  assert {
    condition     = google_storage_notification.landing.event_types == toset(["OBJECT_FINALIZE"]) && google_storage_notification.landing.payload_format == "JSON_API_V1"
    error_message = "landing notification must send OBJECT_FINALIZE as JSON_API_V1"
  }
  assert {
    condition     = google_pubsub_topic.topics["landing-notifications"].name == "landing-notifications"
    error_message = "landing-notifications topic"
  }
  assert {
    condition     = google_pubsub_topic_iam_member.gcs_publisher.role == "roles/pubsub.publisher" && google_pubsub_topic_iam_member.gcs_publisher.topic == "landing-notifications"
    error_message = "GCS service agent must publish to landing-notifications"
  }
}

run "subscriptions_named_with_retention" {
  command = plan
  assert {
    condition     = toset(keys(google_pubsub_subscription.subs)) == toset(["orders-events-bridge", "clickstream-events-bridge", "landing-notifications-snowpipe"])
    error_message = "subscription names"
  }
  assert {
    condition     = alltrue([for s in google_pubsub_subscription.subs : s.ack_deadline_seconds == 60 && s.message_retention_duration == "604800s"])
    error_message = "ack deadline 60s and 7-day retention"
  }
}

run "kafka_off_by_default" {
  command = plan
  assert {
    condition     = var.enable_kafka == false && local.kafka_resource_count == 0
    error_message = "no Kafka resources unless enable_kafka = true"
  }
}

run "supervisors_get_viewer" {
  command = plan
  variables {
    supervisor_emails = ["prof@uni.pl"]
  }
  assert {
    condition     = google_project_iam_member.supervisor["prof@uni.pl"].role == "roles/viewer"
    error_message = "supervisors get roles/viewer on the data project"
  }
}

run "display_name_fits_for_long_team_ids" {
  command = plan
  variables {
    team_id = "team-alpha1"
  }
  assert {
    condition     = length(google_project.data.name) >= 4 && length(google_project.data.name) <= 30
    error_message = "GCP project display names must be 4-30 characters"
  }
}
