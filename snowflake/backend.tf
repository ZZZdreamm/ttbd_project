# Partial config: bucket from ../.state/backend.hcl, prefix "snowflake" (see `mise run snowflake`).
terraform {
  backend "gcs" {}
}
