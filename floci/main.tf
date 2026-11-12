terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

variable "semester" { type = string }
variable "team_id" { type = string }

# No endpoint and no keys in the code: AWS_ENDPOINT_URL / AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY /
# AWS_REGION come from the environment. Without AWS_ENDPOINT_URL the same code would deploy to real AWS.
provider "aws" {
  region = "eu-central-1"
}

resource "aws_s3_bucket" "floci" {
  bucket = "tbd-${var.semester}-${var.team_id}-floci"
}

output "bucket" { value = aws_s3_bucket.floci.bucket }
