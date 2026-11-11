terraform {
  required_version = ">= 1.11"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.9"
    }
  }
  # Local state on purpose: this root creates the bucket that holds the other roots' state.
}
