mock_provider "snowflake" {}
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

variables {
  semester                   = "2026z"
  team_id                    = "07"
  snowflake_account          = "MYORG-TBD07"
  notification_email         = "a@b.pl"
  snowflake_private_key_path = "tests/no-such-key.p8"
}

run "dynamic_iceberg_tables_default_lag_5_minutes" {
  command = plan
  assert {
    condition = alltrue([for e in concat(values(snowflake_execute.dynamic_table), [snowflake_execute.dynamic_table_gold]) :
    strcontains(e.execute, "TARGET_LAG = '5 minutes'") && strcontains(e.execute, "WAREHOUSE = WH_TRANSFORM") && strcontains(e.execute, "DYNAMIC ICEBERG TABLE")])
    error_message = "all streaming DTs: Iceberg, WH_TRANSFORM, 5 minute lag"
  }
  assert {
    condition     = strcontains(snowflake_execute.dynamic_table["SILVER.ORDERS_LATEST"].execute, "BASE_LOCATION = 'silver/orders_latest'")
    error_message = "base location silver/orders_latest"
  }
  assert {
    condition     = toset(keys(snowflake_execute.dynamic_table)) == toset(["SILVER.ORDERS_LATEST", "SILVER.CLICKSTREAM"])
    error_message = "silver DTs"
  }
}

run "gold_rt_selects_no_pii" {
  command = plan
  assert {
    condition = !anytrue([for c in ["CARD_LAST4", "IP_ADDRESS", "SHIPPING_STREET", "SHIPPING_POSTAL_CODE", "CUSTOMER_ID"] :
    strcontains(upper(snowflake_execute.dynamic_table_gold.execute), c)])
    error_message = "gold RT DT must not select PII"
  }
}

run "lag_is_configurable" {
  command = plan
  variables {
    dt_target_lag = "1 minute"
  }
  assert {
    condition     = strcontains(snowflake_execute.dynamic_table["SILVER.CLICKSTREAM"].execute, "TARGET_LAG = '1 minute'")
    error_message = "dt_target_lag variable"
  }
}
