mock_provider "google" {}
mock_provider "google" {
  alias = "billing"
}

variables {
  semester           = "2026Z"
  team_id            = "07"
  billing_account    = "01ABCD-23EF45-6789AB"
  notification_email = "a@b.pl"
}

run "mgmt_project_named_and_billed" {
  command = plan
  assert {
    condition     = google_project.mgmt.project_id == "tbd-2026z-stud07-mgmt"
    error_message = "management project id must be tbd-<semester>-stud<team>-mgmt (lowercase)"
  }
  assert {
    condition     = google_project.mgmt.billing_account == "01ABCD-23EF45-6789AB"
    error_message = "management project must be linked to the billing account"
  }
  assert {
    condition     = google_project.mgmt.auto_create_network == false
    error_message = "no default network"
  }
}

run "state_bucket_is_private_versioned_eu" {
  command = plan
  assert {
    condition     = google_storage_bucket.tfstate.name == "tbd-2026z-stud07-mgmt-tfstate"
    error_message = "state bucket name"
  }
  assert {
    condition     = google_storage_bucket.tfstate.location == "EUROPE-WEST4"
    error_message = "state bucket must be in europe-west4"
  }
  assert {
    condition     = google_storage_bucket.tfstate.versioning[0].enabled == true
    error_message = "state bucket must be versioned"
  }
  assert {
    condition     = google_storage_bucket.tfstate.public_access_prevention == "enforced"
    error_message = "state bucket must enforce public access prevention"
  }
  assert {
    condition     = google_storage_bucket.tfstate.force_destroy == true
    error_message = "state bucket must be destroyable (exercise ends with destroy)"
  }
}

run "budget_is_50_on_billing_account_excluding_credits" {
  command = plan
  assert {
    condition     = google_billing_budget.coupon.amount[0].specified_amount[0].units == "50"
    error_message = "budget amount must be 50"
  }
  assert {
    condition     = google_billing_budget.coupon.budget_filter[0].credit_types_treatment == "EXCLUDE_ALL_CREDITS"
    error_message = "coupon credits must not hide spend"
  }
  assert {
    condition     = sort([for r in google_billing_budget.coupon.threshold_rules : tostring(r.threshold_percent)]) == sort(["0.5", "0.75", "0.9", "1"])
    error_message = "thresholds must be 50/75/90/100%"
  }
  assert {
    condition     = length(coalesce(google_billing_budget.coupon.budget_filter[0].projects, [])) == 0
    error_message = "budget must cover the whole billing account (no project filter)"
  }
}

run "no_supervisors_by_default" {
  command = plan
  assert {
    condition     = length(google_project_iam_member.supervisor) == 0
    error_message = "no supervisor IAM members when supervisor_emails is empty"
  }
}

run "supervisors_get_viewer" {
  command = plan
  variables {
    supervisor_emails = ["prof@uni.pl"]
  }
  assert {
    condition     = google_project_iam_member.supervisor["prof@uni.pl"].role == "roles/viewer" && google_project_iam_member.supervisor["prof@uni.pl"].member == "user:prof@uni.pl"
    error_message = "supervisors get roles/viewer"
  }
}

run "display_name_fits_for_long_team_ids" {
  command = plan
  variables {
    team_id = "team-alpha1"
  }
  assert {
    condition     = length(google_project.mgmt.name) >= 4 && length(google_project.mgmt.name) <= 30
    error_message = "GCP project display names must be 4-30 characters"
  }
}
