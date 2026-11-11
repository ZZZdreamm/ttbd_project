output "mgmt_project_id" {
  value = google_project.mgmt.project_id
}

output "state_bucket" {
  value = google_storage_bucket.tfstate.name
}
