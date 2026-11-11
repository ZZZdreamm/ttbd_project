output "pat_files" {
  value = [for f in local_sensitive_file.pat : f.filename]
}

output "ingest_key_file" {
  value = local_sensitive_file.ingest_key.filename
}

output "external_volume_service_account" {
  value = local.ev_service_account
}
