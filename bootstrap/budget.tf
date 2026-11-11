resource "google_monitoring_notification_channel" "budget_email" {
  project      = google_project.mgmt.project_id
  display_name = "Budget alerts (${var.notification_email})"
  type         = "email"
  labels = {
    email_address = var.notification_email
  }
  depends_on = [google_project_service.apis]
}

# Covers the whole coupon billing account (both projects). GCP budgets alert; they don't stop spend.
resource "google_billing_budget" "coupon" {
  provider        = google.billing
  billing_account = var.billing_account
  display_name    = "TBD ${local.prefix} coupon budget"

  budget_filter {
    credit_types_treatment = "EXCLUDE_ALL_CREDITS"
  }

  amount {
    specified_amount {
      units = tostring(var.budget_amount)
    }
  }

  dynamic "threshold_rules" {
    for_each = [0.5, 0.75, 0.9, 1.0]
    content {
      threshold_percent = threshold_rules.value
      spend_basis       = "CURRENT_SPEND"
    }
  }

  all_updates_rule {
    monitoring_notification_channels = [google_monitoring_notification_channel.budget_email.id]
    disable_default_iam_recipients   = false
  }

  depends_on = [google_project_service.apis]
}
