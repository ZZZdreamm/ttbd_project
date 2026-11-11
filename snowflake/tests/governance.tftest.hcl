mock_provider "snowflake" {
  override_during = plan
  mock_resource "snowflake_external_volume" {
    defaults = {
      describe_output = [{ active = "", allow_writes = "true", comment = "", storage_locations = [{ name = "gcs-europe-west4", storage_provider = "GCS", storage_base_url = "gcs://x/iceberg/", storage_allowed_locations = [], encryption_type = "NONE", azure_storage_location = [], s3_storage_location = [], s3_compat_storage_location = [], gcs_storage_location = [{ encryption_kms_key_id = "", storage_gcp_service_account = "ev-sa@sf.iam.gserviceaccount.com" }] }] }]
    }
  }
  mock_resource "snowflake_storage_integration_gcs" {
    defaults = {
      describe_output = [{ service_account = "si-sa@sf.iam.gserviceaccount.com", allowed_locations = [], blocked_locations = [], comment = "", enabled = true, id = "", provider = "GCS", use_privatelink_endpoint = false }]
    }
  }
  mock_resource "snowflake_notification_integration" {
    defaults = {
      gcp_pubsub_service_account = "ni-sa@sf.iam.gserviceaccount.com"
    }
  }
}
mock_provider "snowflake" {
  alias = "pipeline"
}
mock_provider "google" {}
mock_provider "tls" {}
mock_provider "local" {}

override_data {
  target = data.terraform_remote_state.gcp
  values = {
    outputs = {
      data_project_id                   = "tbd-2026z-stud07-data"
      landing_bucket                    = "tbd-2026z-stud07-data-landing"
      lakehouse_bucket                  = "tbd-2026z-stud07-data-lakehouse"
      landing_notification_subscription = "projects/tbd-2026z-stud07-data/subscriptions/landing-notifications-snowpipe"
    }
  }
}

override_resource {
  target          = snowflake_tag.pii_type
  override_during = plan
  values = {
    fully_qualified_name = "\"LAKEHOUSE\".\"GOVERNANCE\".\"PII_TYPE\""
  }
}

override_resource {
  target          = snowflake_masking_policy.pii_string
  override_during = plan
  values = {
    fully_qualified_name = "\"LAKEHOUSE\".\"GOVERNANCE\".\"MP_PII_STRING\""
  }
}

override_resource {
  target          = snowflake_masking_policy.pii_date
  override_during = plan
  values = {
    fully_qualified_name = "\"LAKEHOUSE\".\"GOVERNANCE\".\"MP_PII_DATE\""
  }
}

variables {
  semester                   = "2026z"
  team_id                    = "07"
  snowflake_account          = "MYORG-TBD07"
  notification_email         = "a@b.pl"
  snowflake_private_key_path = "tests/no-such-key.p8" # mock providers never read it
}

run "pii_tag_with_propagation" {
  command = plan
  assert {
    condition     = snowflake_tag.pii_type.name == "PII_TYPE" && snowflake_tag.pii_type.schema == "GOVERNANCE"
    error_message = "tag LAKEHOUSE.GOVERNANCE.PII_TYPE"
  }
  assert {
    condition     = toset(snowflake_tag.pii_type.ordered_allowed_values) == toset(["NAME", "EMAIL", "PHONE", "ADDRESS", "DOB", "IP", "CARD"])
    error_message = "allowed values"
  }
  assert {
    condition     = snowflake_tag.pii_type.propagate == "ON_DEPENDENCY_AND_DATA_MOVEMENT"
    error_message = "tag must propagate to dynamic tables and dbt models"
  }
  assert {
    condition     = strcontains(snowflake_execute.tag_masking["string"].execute, "SET MASKING POLICY \"LAKEHOUSE\".\"GOVERNANCE\".\"MP_PII_STRING\"") && strcontains(snowflake_execute.tag_masking["date"].execute, "SET MASKING POLICY \"LAKEHOUSE\".\"GOVERNANCE\".\"MP_PII_DATE\"")
    error_message = "both MP_PII_STRING and MP_PII_DATE bound to the tag"
  }
}

run "policies_use_current_role_and_tag_value" {
  command = plan
  assert {
    condition     = snowflake_masking_policy.pii_string.name == "MP_PII_STRING" && snowflake_masking_policy.pii_string.return_data_type == "VARCHAR"
    error_message = "MP_PII_STRING"
  }
  assert {
    condition     = snowflake_masking_policy.pii_date.name == "MP_PII_DATE" && snowflake_masking_policy.pii_date.return_data_type == "DATE"
    error_message = "MP_PII_DATE"
  }
  assert {
    condition = alltrue([for b in [snowflake_masking_policy.pii_string.body, snowflake_masking_policy.pii_date.body, snowflake_row_access_policy.support_country.body] :
    strcontains(b, "CURRENT_ROLE()") && !strcontains(b, "IS_ROLE_IN_SESSION")])
    error_message = "policies must use CURRENT_ROLE() (secondary roles would leak through IS_ROLE_IN_SESSION)"
  }
  assert {
    condition     = strcontains(snowflake_masking_policy.pii_string.body, "SYSTEM$GET_TAG_ON_CURRENT_COLUMN('LAKEHOUSE.GOVERNANCE.PII_TYPE')")
    error_message = "string policy branches on the tag value"
  }
  assert {
    condition     = strcontains(snowflake_row_access_policy.support_country.body, "SUPPORT_COUNTRY_MAP") && strcontains(snowflake_row_access_policy.support_country.body, "CURRENT_USER()")
    error_message = "RAP maps CURRENT_USER() to countries"
  }
}

run "pii_columns_tagged_exactly" {
  command = plan
  assert {
    condition     = snowflake_tag_association.pii["NAME"].object_identifiers == toset(["\"LAKEHOUSE\".\"BRONZE\".\"CUSTOMERS_RAW\".\"FIRST_NAME\"", "\"LAKEHOUSE\".\"BRONZE\".\"CUSTOMERS_RAW\".\"LAST_NAME\""]) && snowflake_tag_association.pii["NAME"].object_type == "ICEBERG TABLE COLUMN" && snowflake_tag_association.pii["NAME"].tag_value == "NAME"
    error_message = "NAME columns tagged exactly"
  }
  assert {
    condition     = snowflake_tag_association.pii["EMAIL"].object_identifiers == toset(["\"LAKEHOUSE\".\"BRONZE\".\"CUSTOMERS_RAW\".\"EMAIL\""]) && snowflake_tag_association.pii["EMAIL"].object_type == "ICEBERG TABLE COLUMN" && snowflake_tag_association.pii["EMAIL"].tag_value == "EMAIL"
    error_message = "EMAIL columns tagged exactly"
  }
  assert {
    condition     = snowflake_tag_association.pii["PHONE"].object_identifiers == toset(["\"LAKEHOUSE\".\"BRONZE\".\"CUSTOMERS_RAW\".\"PHONE\""]) && snowflake_tag_association.pii["PHONE"].object_type == "ICEBERG TABLE COLUMN" && snowflake_tag_association.pii["PHONE"].tag_value == "PHONE"
    error_message = "PHONE columns tagged exactly"
  }
  assert {
    condition     = snowflake_tag_association.pii["ADDRESS"].object_identifiers == toset(["\"LAKEHOUSE\".\"BRONZE\".\"CUSTOMERS_RAW\".\"STREET\"", "\"LAKEHOUSE\".\"BRONZE\".\"CUSTOMERS_RAW\".\"POSTAL_CODE\"", "\"LAKEHOUSE\".\"BRONZE\".\"ORDERS_EVENTS\".\"SHIPPING_STREET\"", "\"LAKEHOUSE\".\"BRONZE\".\"ORDERS_EVENTS\".\"SHIPPING_POSTAL_CODE\""]) && snowflake_tag_association.pii["ADDRESS"].object_type == "ICEBERG TABLE COLUMN" && snowflake_tag_association.pii["ADDRESS"].tag_value == "ADDRESS"
    error_message = "ADDRESS columns tagged exactly"
  }
  assert {
    condition     = snowflake_tag_association.pii["DOB"].object_identifiers == toset(["\"LAKEHOUSE\".\"BRONZE\".\"CUSTOMERS_RAW\".\"DATE_OF_BIRTH\""]) && snowflake_tag_association.pii["DOB"].object_type == "ICEBERG TABLE COLUMN" && snowflake_tag_association.pii["DOB"].tag_value == "DOB"
    error_message = "DOB columns tagged exactly"
  }
  assert {
    condition     = snowflake_tag_association.pii["IP"].object_identifiers == toset(["\"LAKEHOUSE\".\"BRONZE\".\"ORDERS_EVENTS\".\"IP_ADDRESS\"", "\"LAKEHOUSE\".\"BRONZE\".\"CLICKSTREAM_EVENTS\".\"IP_ADDRESS\""]) && snowflake_tag_association.pii["IP"].object_type == "ICEBERG TABLE COLUMN" && snowflake_tag_association.pii["IP"].tag_value == "IP"
    error_message = "IP columns tagged exactly"
  }
  assert {
    condition     = snowflake_tag_association.pii["CARD"].object_identifiers == toset(["\"LAKEHOUSE\".\"BRONZE\".\"ORDERS_EVENTS\".\"CARD_LAST4\""]) && snowflake_tag_association.pii["CARD"].object_type == "ICEBERG TABLE COLUMN" && snowflake_tag_association.pii["CARD"].tag_value == "CARD"
    error_message = "CARD columns tagged exactly"
  }
}

run "bronze_tables_are_snowflake_iceberg" {
  command = plan
  assert {
    condition     = toset(keys(snowflake_iceberg_table.bronze)) == toset(["ORDERS_EVENTS", "CLICKSTREAM_EVENTS", "CUSTOMERS_RAW", "PRODUCTS_RAW", "RETURNS_RAW"])
    error_message = "bronze tables"
  }
  assert {
    condition = alltrue([for k, t in snowflake_iceberg_table.bronze :
    t.external_volume == "EV_LAKEHOUSE" && t.catalog == "SNOWFLAKE" && t.base_location == "bronze/${lower(k)}" && t.schema == "BRONZE"])
    error_message = "EV_LAKEHOUSE, SNOWFLAKE catalog, base_location bronze/<table>"
  }
  assert {
    condition     = contains([for c in snowflake_iceberg_table.bronze["CUSTOMERS_RAW"].column : c.name], "_FILE") && contains([for c in snowflake_iceberg_table.bronze["ORDERS_EVENTS"].column : c.name], "_INGESTED_AT")
    error_message = "ingestion metadata columns"
  }
  assert {
    # A fresh volume fails table creation (091369 "retry to setup external volume") until GCS IAM
    # has propagated; bronze tables wait for SYSTEM$VERIFY_EXTERNAL_VOLUME to pass.
    condition     = terraform_data.external_volume_ready.input == "EV_LAKEHOUSE"
    error_message = "external volume readiness check before the bronze tables"
  }
}

run "rap_key_columns_never_tagged" {
  command = plan
  assert {
    condition     = length([for v, ids in local.pii_column_ids : v if anytrue([for id in ids : can(regex("COUNTRY", id))])]) == 0
    error_message = "country columns are row-access keys and must never carry PII_TYPE"
  }
}
