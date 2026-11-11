locals {
  prefix     = lower("tbd-${var.semester}-stud${var.team_id}")
  project_id = "${local.prefix}-mgmt"
}

provider "google" {
  project = local.project_id
  region  = var.region
}

# Budgets API needs a quota project; use the management project itself.
provider "google" {
  alias                 = "billing"
  project               = local.project_id
  region                = var.region
  billing_project       = local.project_id
  user_project_override = true
}

resource "google_project" "mgmt" {
  name                = local.project_id # display names are limited to 30 chars, like IDs
  project_id          = local.project_id
  billing_account     = var.billing_account
  auto_create_network = false
  deletion_policy     = "DELETE"
}

resource "google_project_service" "apis" {
  for_each = toset([
    "cloudbilling.googleapis.com",
    "billingbudgets.googleapis.com",
    "monitoring.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "iam.googleapis.com",
    "storage.googleapis.com",
    "pubsub.googleapis.com",
  ])
  project            = google_project.mgmt.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "tfstate" {
  project                     = google_project.mgmt.project_id
  name                        = "${local.project_id}-tfstate"
  location                    = upper(var.region)
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true

  versioning {
    enabled = true
  }

  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "supervisor" {
  for_each = toset(var.supervisor_emails)
  project  = google_project.mgmt.project_id
  role     = "roles/viewer"
  member   = "user:${each.value}"
}
