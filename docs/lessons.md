# What this exercise teaches

## 1. Masking lives in the catalog, not in the files

PII columns carry a tag, `LAKEHOUSE.GOVERNANCE.PII_TYPE`. Two masking policies are bound to the tag:
one for text, one for dates. A tag can carry only one policy per data type, so each policy reads the
tag's value with `SYSTEM$GET_TAG_ON_CURRENT_COLUMN` to decide how to mask. Any newly tagged column
is masked automatically.

- **Inside Snowflake**, the policies apply to every query.
- **Spark via Horizon**: Iceberg ≥ 1.11 asks Horizon to plan the scan (the *Scan Plan API*).
  Snowflake evaluates the masking and row access policies for the PAT's role and user, then hands
  Spark a filtered, masked dataset.
- **DuckDB** can't do server-side scan planning yet, so Horizon **refuses** it protected tables. It
  reads only the PII-free gold tables.
- **The raw Parquet files in your GCS bucket are not masked.** Anyone with bucket access sees
  everything, so bucket IAM is part of governance. Scan Plan writes its filtered datasets to the
  bucket too, and keeps them for up to 24 hours.

## 2. Only the primary role counts

The policies use `CURRENT_ROLE()`. Users default to `DEFAULT_SECONDARY_ROLES = ('ALL')`, which
makes every granted role active. A policy written with `IS_ROLE_IN_SESSION('PII_ADMIN')` would
unmask data for anyone who also holds `PII_ADMIN`. We saw exactly this happen while building the
exercise. The service users here are created with no secondary roles.

## 3. Explicit tags vs lineage-driven tags

- **Batch (dbt):** columns declare `meta: {pii_type: EMAIL}` in the model YAML. A post-hook turns
  that into a Snowflake tag after every build.
- **Streaming (dynamic tables):** the tag is created with
  `PROPAGATE = ON_DEPENDENCY_AND_DATA_MOVEMENT`. Tags on bronze columns flow automatically into the
  dynamic tables and dbt models built from them, and the masking follows.

Compare the two in `SHOW TAGS` and `TAG_REFERENCES_ALL_COLUMNS`. The `apply_method` is `MANUAL`
for tags from dbt and `PROPAGATED` for tags from lineage.

## 4. The refresh-role rule

A dynamic table refreshes as its **owner role**, and masking applies to that role during the
refresh. If the owner weren't exempt, the table would store values that are *already masked*.
`PIPELINE_ADMIN` owns all pipeline objects and is exempt, so derived tables hold real data and
masking happens at read time.

## 5. Row access needs unmasked keys

`RAP_SUPPORT_COUNTRY` lets `SUPPORT_USER` see only the countries mapped to them in
`GOVERNANCE.SUPPORT_COUNTRY_MAP`. A column that a masking policy covers can't be the argument of a
row access policy, so `country` must never be tagged as PII.

## 6. Why gold is PII-free

Gold uses `customer_key = sha2(customer_id || salt)` and contains no names, emails or addresses. It
can therefore be read by any engine, including DuckDB, without policy enforcement. That's the usual
pattern for sharing data.

## 7. Paying only for what you use

- Resource monitors stop **warehouses** only.
- Serverless features (Snowpipe, Snowpipe Streaming, Scan Plan) need a **budget**. Ours calls a
  stop procedure.
- Dynamic-table lag is a **cost dial**: 5 minutes is cheap, 1 minute keeps a warehouse busy all day.
- Stop pipelines when you aren't working (`mise run stop`).

## 8. Exactly once, from at-least-once

The bridge acknowledges a Pub/Sub message only after Snowflake has committed the batch that holds
it. If the bridge crashes, the messages are delivered again and bronze gets duplicates. Silver
removes them by `event_id`, and the latest status follows `event_ts`, not arrival order.
