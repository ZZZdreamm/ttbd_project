variable "semester" {
  type        = string
  description = "Semester label (TF_VAR_semester)"
}

variable "team_id" {
  type        = string
  description = "Team id (TF_VAR_team_id)"
}

variable "snowflake_account" {
  type        = string
  description = "Snowflake <org>-<account> identifier (SNOWFLAKE_ACCOUNT in .env)"
  validation {
    condition     = can(regex("^[A-Za-z0-9]+-[A-Za-z0-9_]+$", var.snowflake_account))
    error_message = "snowflake_account must look like ORG-ACCOUNT."
  }
}

variable "notification_email" {
  type        = string
  description = "Verified email of the trial admin; receives Snowflake budget alerts"
}

variable "snowflake_private_key_path" {
  type        = string
  default     = "../.secrets/terraform_svc.p8"
  description = "TERRAFORM_SVC private key written by `mise run sf:keygen`"
}

variable "secrets_dir" {
  type        = string
  default     = "../.secrets"
  description = "Where generated PATs and the ingest key are written (gitignored)"
}

variable "credit_cap" {
  type        = number
  default     = 12
  description = "Snowflake credits allowed (~$47 at $3.90/credit in GCP Europe West 4)"
}

variable "pat_days_to_expiry" {
  type        = number
  default     = 30
  description = "Lifetime of the demo users' PATs (a trial lasts 30 days)"
}

variable "dt_target_lag" {
  type        = string
  default     = "5 minutes"
  description = "Target lag of the streaming dynamic tables. 1 minute keeps WH_TRANSFORM busy almost constantly (~24 credits/day); use it only during a live demo."
}
