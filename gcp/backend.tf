# Partial config: bucket comes from ../.state/backend.hcl (written by `mise run bootstrap`), prefix "gcp".
terraform {
  backend "gcs" {}
}
