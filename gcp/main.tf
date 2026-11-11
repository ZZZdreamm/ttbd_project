locals {
  prefix     = lower("tbd-${var.semester}-stud${var.team_id}")
  project_id = "${local.prefix}-data"
}

provider "google" {
  project = local.project_id
  region  = var.region
}

resource "google_project" "data" {
  name                = local.project_id # display names are limited to 30 chars, like IDs
  project_id          = local.project_id
  billing_account     = var.billing_account
  auto_create_network = false
  deletion_policy     = "DELETE"
}

resource "google_project_service" "apis" {
  for_each = toset([
    "storage.googleapis.com",
    "pubsub.googleapis.com",
    "monitoring.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
  ])
  project            = google_project.data.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_project_iam_member" "supervisor" {
  for_each = toset(var.supervisor_emails)
  project  = google_project.data.project_id
  role     = "roles/viewer"
  member   = "user:${each.value}"
}
