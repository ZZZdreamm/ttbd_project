terraform {
  required_version = ">= 1.11"
  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 2.22"
    }
    google = {
      source  = "hashicorp/google"
      version = "~> 8.9"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.1"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}
