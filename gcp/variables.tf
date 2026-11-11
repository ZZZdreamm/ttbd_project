variable "semester" {
  type        = string
  description = "Semester label, e.g. 2026z (from TF_VAR_semester)"
}

variable "team_id" {
  type        = string
  description = "Team number or short name (from TF_VAR_team_id)"
}

variable "billing_account" {
  type        = string
  description = "Billing account ID created by redeeming the GCP coupon"
}

variable "supervisor_emails" {
  type        = list(string)
  default     = []
  description = "Instructors who get roles/viewer on the projects"
}

variable "region" {
  type        = string
  default     = "europe-west4"
  description = "Region for every resource in the exercise"
}

variable "enable_kafka" {
  type        = bool
  default     = false
  description = "Optional Kafka lab (Task 17). Costs money per hour; turn on for one session only."
}
