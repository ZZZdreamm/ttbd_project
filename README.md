# TBD Lakehouse exercise

Build a governed **Iceberg lakehouse** on **Google Cloud + Snowflake** with two ingestion paths,
two transformation styles and attribute-based masking. Then prove it works with one command and
tear it all down.

```
 [gen:stream] ─► Pub/Sub ─► [bridge] ─► Snowpipe Streaming ─► BRONZE ─► dynamic tables ─► SILVER/GOLD
 [gen:batch]  ─► GCS landing ─► GCS event ─► Snowpipe auto-ingest ─► BRONZE ─► dbt (task) ─► SILVER/GOLD
                                   all layers: Snowflake-managed Iceberg tables in your GCS bucket
 [Spark / DuckDB (marimo lab, Docker)] ─► Snowflake Horizon (Iceberg REST) ─► the same Iceberg files

 [ … ] runs locally on your laptop (started with mise run …); everything else runs in GCP or Snowflake.
```

Everything runs in **one EU region**: GCP `europe-west4` (Netherlands) and Snowflake on
*Google Cloud Europe West 4 (Netherlands)*. This is the cheapest EU option: $3.90 per credit for
Enterprise.

**One student per team** runs everything from their own laptop.

## What you need

- macOS or Linux, [Docker](https://docs.docker.com/get-docker/) (about 4 GB RAM free for the lab)
  and [mise](https://mise.jdx.dev/getting-started.html).
- A **personal Google account** (Gmail) for GCP.
- Your **school email** to request the GCP coupon.

## 1. Tools

```bash
mise trust && mise install      # terraform, gcloud, snow, uv/python, dbt, duckdb (pinned)
uv sync
```

## 2. GCP coupon → billing account

1. Request the coupon **early**. The request deadline is **2027-02-28**, and coupons are valid until
   2027-10-28. Go to the
   [coupon retrieval link](https://gcp.secure.force.com/GCPEDU?cid=8bq2sIm5f58F773KNNf9Prc4dvitlRedoEN02nvlvb%2BJqE%2B9o%2FnD6xuT7Fo8ujLN/),
   enter your school email (one coupon per address), confirm the email, then redeem the code with
   your personal Google account.
2. Note the **billing account ID** (Console → Billing → Account management, e.g. `01ABCD-23EF45-6789AB`).

## 3. Snowflake trial

Create it **only when you're ready to start**: a trial lasts 30 days.
[Sign up](https://signup.snowflake.com/) with **Enterprise**, **Google Cloud** and **Europe West 4
(Netherlands)**. Use an email you can read: budget alerts go there.

## 4. `.env`

```bash
cp .env.example .env    # then fill it in
mise run config         # validates it and prints your project names
```

| Variable | Example | Notes |
|---|---|---|
| `TF_VAR_semester` | `2026z` | lowercase letters, digits, hyphens |
| `TF_VAR_team_id` | `07` | project IDs become `tbd-<semester>-stud<team>-mgmt/-data` (≤ 30 chars, so at most 11 for the team) |
| `TF_VAR_billing_account` | `01ABCD-23EF45-6789AB` | from step 2 |
| `TF_VAR_notification_email` | the email of your Snowflake trial | GCP + Snowflake budget alerts |
| `TF_VAR_supervisor_emails` | `["teacher@uni.pl"]` | optional: read-only access to your GCP projects |
| `SNOWFLAKE_ACCOUNT` | `ABCDEFG-XY12345` | Snowsight → account menu → *View account details* → *Account identifier* |

## 5. Log in

```bash
gcloud auth login                       # your personal Google account
gcloud auth application-default login   # same account
mise run sf:keygen                      # creates .secrets/terraform_svc.p8 and prints SQL
```

In Snowsight (as the trial admin), open a SQL worksheet. Run the printed SQL **one line at a time**:
put the cursor on a line and press Ctrl/Cmd+Enter. Each line says what it should print. The
`DESC USER` line must show the same `RSA_PUBLIC_KEY_FP` that `sf:keygen` printed. Then check:

```bash
mise exec -- snow sql -q "select current_user()"    # → TERRAFORM_SVC
```

## 6. Build everything

```bash
mise run up     # bootstrap → gcp → snowflake → dbt:deploy → dcm  (~10 min)
```

Each Terraform step shows its plan and asks before applying: read it, then type `yes` (on the first
run `snowflake` asks twice: a small apply for the pipeline login, then the rest).
Or step by step: `mise run bootstrap`,
`mise run gcp`, `mise run snowflake`, `mise run dbt:deploy`, `mise run dcm`. Every step is safe to
re-run: a second run reports `No changes`.

## 7. Run it

Use separate terminals:

```bash
mise run gen:batch      # drops customer/product/return files every 3-5 min
mise run gen:stream     # order + click events to Pub/Sub (Ctrl-C to stop)
mise run bridge         # Pub/Sub → Snowpipe Streaming (Ctrl-C to stop)
mise run lab            # Spark + DuckDB notebooks → http://localhost:2718 (LAB_PORT=... to change)
```

Let data flow for **20–30 minutes**. dbt runs every 15 minutes (`mise run dbt:run` runs it now), and
the dynamic tables refresh every 5 minutes. Then:

```bash
mise run test           # one PASS/FAIL row per check (takes ~8 min)
```

In the lab, `01_parity` shows Snowflake, Spark and DuckDB results side by side, and `02_masking`
shows masking per role through Horizon. Nothing runs on its own: run each cell yourself (▶ or
Shift+Enter, top to bottom). After you change a dropdown, the cells below turn stale; run them again.

**At the end of every session:** `mise run stop` (`mise run start` resumes). `mise run cost` shows
the credits used so far.

## 8. Success criteria

- [ ] All Terraform roots applied from a clean billing account and a fresh trial (`mise run up`).
- [ ] Batch path (files → Snowpipe → dbt) and streaming path (Pub/Sub → Snowpipe Streaming →
      dynamic tables) both put data in gold.
- [ ] Gold queried from Spark **and** DuckDB in marimo, with the same results as Snowflake
      (check 4).
- [ ] Masking verified per role in Snowflake and in Spark via Horizon (checks 5 and 6).
- [ ] `mise run test` shows 7 × PASS.
- [ ] Exercise (step 9) uploaded: the lineage report and the masking notebook, both as PDF.
- [ ] Everything destroyed (step 10) and `mise run verify-destroyed` says *All clean*.
- [ ] floci part (step 11) uploaded: `<team_id>-floci.pdf`.

## 9. Exercise (before you destroy)

Do both tasks while everything is still running, because both need live data. You'll upload two
PDFs to the course assignment: `<team_id>-lineage.pdf` and `<team_id>-masking.pdf`.

### Task 1: lineage report

Write a short report (2–4 pages) that follows one record from its generator to gold, on both paths:

- **Batch:** a customer change from `mise run gen:batch` to a gold table built from it, for
  example `GOLD.CUSTOMER_LTV`.
- **Streaming:** an order event from `mise run gen:stream` to `GOLD.ORDERS_BY_COUNTRY_STATUS_RT`.

For every step, give:

- the object (bucket, topic, pipe, table, task, …) and what moves the data into it
- which tool created it (Terraform, DCM, dbt, or Python in `src/`) and the file that defines it
- how long the step takes: its schedule, its target lag, or what you measured
- the table format (Iceberg or not), and which engines can read it

Then:

- **Draw the lineage graph** of each path. Any tool is fine, and a Snowsight screenshot counts.
- **Follow one PII column on each path:** `email` (batch) and `ip_address` (streaming). Show where
  the `PII_TYPE` tag is set or propagated (`apply_method` `MANUAL` vs `PROPAGATED`), and where the
  masking is applied.
- **Compare the two paths:** latency, cost, and where duplicates are removed.

Where to look:

- Snowsight: **Catalog → Database Explorer →** a table **→ Lineage**
- `SELECT * FROM TABLE(SNOWFLAKE.CORE.GET_LINEAGE('LAKEHOUSE.GOLD.<table>', 'TABLE', 'UPSTREAM', 5));`
- `SELECT * FROM TABLE(LAKEHOUSE.INFORMATION_SCHEMA.TAG_REFERENCES_ALL_COLUMNS('LAKEHOUSE.SILVER.ORDERS_LATEST', 'TABLE'));`
- the code: `src/tbd_lakehouse/`, `gcp/`, `dcm/sources/definitions/`, `snowflake/bronze.tf`,
  `snowflake/dynamic_tables.tf`, `dbt/models/`

Snowflake only sees its own objects. Add the steps outside it (GCS, Pub/Sub, the bridge) from the
code.

### Task 2: your own role and masking

Scenario: a marketing team may segment customers but must not be able to identify them. Add a role
for it (for example `MARKETING`, with the user `MARKETING_USER`) and decide what it sees.

1. **Add the role and its user in Terraform** (`snowflake/roles.tf`, `snowflake/users.tf`). Adding
   them to `local.roles` and `local.demo_users` creates the user and its PAT (in `.secrets/`), and
   most of the grants. Compare with `SUPPORT` to find what else a reading role needs: look at the
   external volume, the row access policy, and grants on tables that already exist (future grants
   only cover new objects). Apply with `mise run snowflake`.
2. **Design a masking function for each `PII_TYPE` value** (`NAME`, `EMAIL`, `PHONE`, `ADDRESS`,
   `DOB`, `IP`, `CARD`). Use at least three different functions: one must mask every second
   character, and one must be your own idea. Some ideas:

   | Function | SQL (`val` is the column value) | Example |
   |---|---|---|
   | Every second character | `REGEXP_REPLACE(val, '(.).', '\\1*')` | `Kowalski` → `K*w*l*k*` |
   | First and last character only | `LEFT(val, 1) \|\| REPEAT('*', GREATEST(LENGTH(val) - 2, 0)) \|\| RIGHT(val, 1)` | `Kowalski` → `K******i` |
   | Pseudonym: the same input always gives the same output, so you can still count and join | `LEFT(SHA2(LOWER(val)), 12)` | `jan@example.com` → 12 hex characters |
   | Year only (`DOB`, in the date policy) | `DATE_FROM_PARTS(YEAR(val), 1, 1)` | `1987-06-14` → `1987-01-01` |
   | Network only (`IP`) | `SPLIT_PART(val, '.', 1) \|\| '.' \|\| SPLIT_PART(val, '.', 2) \|\| '.0.0'` | `10.1.2.3` → `10.1.0.0` |

3. **Add your functions to the masking policies.** The `PII_TYPE` tag can carry only one masking
   policy per data type, so your role gets its own branch (`WHEN CURRENT_ROLE() = 'MARKETING' …`)
   in `snowflake/sql/mp_pii_string.sql` and `snowflake/sql/mp_pii_date.sql`. Apply with
   `mise run snowflake`. If you write the functions as SQL UDFs in `GOVERNANCE` and call them from
   the policy, check that Spark still gets the masked values through Horizon.
4. **Prove it in a new notebook,** `lab/notebooks/03_masking_<team_id>.py`. Create it from the
   lab's home page, or start from a copy of `02_masking.py`. The notebook must:
   - register your user for the lab helpers:
     `from tbd_lakehouse.lab import engines; engines.DEMO_ROLES["MARKETING_USER"] = "MARKETING"`
   - read the same rows of `SILVER.CUSTOMERS_CURRENT` (batch) and `SILVER.ORDERS_LATEST`
     (streaming) as `PII_ADMIN_USER` (raw values) and as your user, in **Snowflake and in Spark**
     (`snowflake_df_as`, `spark_df`)
   - check in code that every masked value equals your function applied to the raw value (write
     each function again in Python), and show PASS or FAIL per column
   - show which `CUSTOMERS_CURRENT` rows your role sees, and explain why (row access policy)
   - show that DuckDB is still refused, and that `SUPPORT_USER` sees what it did before
5. **Check you broke nothing:** `mise run test` still shows 7 × PASS.
6. **Render it to PDF and upload it.** Run every cell from top to bottom. Then use the notebook
   menu (**⋯**, top right) → **Download → Download as HTML**, open the file in your browser, and
   print it to PDF (Cmd/Ctrl+P → *Save as PDF*). marimo's own *Download as PDF* needs packages the
   lab image doesn't have. Upload the PDF as `<team_id>-masking.pdf`.

## 10. Destroy

```bash
mise run destroy           # asks you to type 'destroy'
mise run verify-destroyed
```

GCP keeps deleted projects for 30 days, and **their IDs can't be reused until then**. If you want to
rebuild after destroying, use a new `TF_VAR_team_id`, and rerun the SQL from `mise run sf:keygen`
(step 5): destroy also drops `WH_QUERY`, the warehouse Terraform logs in with. The Snowflake trial
expires on its own.

## 11. Local cloud emulator (floci)

Real clouds cost money, and each `apply` takes minutes. A **cloud emulator** runs a fake cloud on
your laptop. It answers the same APIs, so the same Terraform code runs against it for free, in
seconds. [floci](https://github.com/floci-io/floci) emulates AWS. Try it with one bucket.

1. Create `floci/compose.yml` and start floci:

   ```yaml
   services:
     floci:
       image: floci/floci:2.4.0
       ports: ["4566:4566"]
       volumes:
         - /var/run/docker.sock:/var/run/docker.sock   # floci runs its web console in a container
       environment:
         FLOCI_RUN_AS_ROOT: "true"                     # Linux: lets floci use the Docker socket
   ```

   ```bash
   cd floci
   docker compose up -d
   export AWS_ENDPOINT_URL=http://localhost.floci.io:4566 AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_REGION=eu-central-1
   ```

   `AWS_ENDPOINT_URL` sends every AWS call to floci. `*.localhost.floci.io` resolves to
   `127.0.0.1`. Without this variable, the same code would deploy to real AWS.

2. Write `floci/main.tf` with the `hashicorp/aws` provider (`~> 6.0`, region `eu-central-1`, no
   endpoint or keys in the code) and one `aws_s3_bucket` named `tbd-<semester>-<team_id>-floci`.
   Then:

   ```bash
   mise exec -- terraform init
   mise exec -- terraform apply
   ```

3. Open <http://localhost:4566/_floci/ui>. The first visit starts the console, which takes about
   30 s. Go to **Storage** and find your bucket.

4. Clean up:

   ```bash
   mise exec -- terraform destroy
   docker rm -f floci-aws-ui      # the console container floci started
   docker compose down
   ```

Upload `<team_id>-floci.pdf` with:

1. a screenshot of the floci console showing your bucket;
2. a short answer: how could an emulator like this help in this project (cost, development time,
   CI), and what can't it replace? What would you still have to test on the real cloud?

## Costs and guardrails

| What | Cost | Guardrail |
|---|---|---|
| Snowflake warehouses (X-Small, 1 credit/h, auto-suspend 60 s) | about 0.5–1 credit per 3-hour session | resource monitor `RM_LAB`: 12 credits (~$47), lifetime, suspends warehouses at 100% |
| Snowflake serverless (Snowpipe, Snowpipe Streaming, Horizon scan plans) | ≈ 0 at lab volumes (Snowpipe 0.0037 credits/GB, Scan Plan = serverless compute) | account budget of 12 credits calls `OPS.STOP_ALL()` at 95% |
| Dynamic tables | target lag 5 min (a 1-minute lag ≈ 24 credits/day!) | `mise run stop` suspends them |
| GCP (GCS, Pub/Sub) | cents | $50 budget with email alerts (alerts only: GCP budgets don't stop spend) |

Usage views lag by up to about 3 hours, so the stop can overshoot slightly. Always run
`mise run stop`.

## Troubleshooting

- **`JWT token is invalid`** after `sf:keygen`: the user doesn't exist or has a different key. Rerun
  the printed SQL **line by line** in a worksheet set to `ACCOUNTADMIN`, and compare
  `RSA_PUBLIC_KEY_FP`.
- **`USER_PROJECT_DENIED`** from gcloud: your global gcloud config has a quota project. mise sets
  `CLOUDSDK_BILLING_QUOTA_PROJECT=LEGACY`, so run commands through mise.
- **A file in the landing bucket never reached bronze:** files uploaded before the pipes existed
  aren't picked up automatically. `mise run dcm` refreshes the pipes. Snowpipe latency is usually
  1–4 minutes.
- **`mise run test` says *lab not running*:** start it with `mise run lab`.
- **Bridge prints `append failed`** after `mise run stop`: expected. It reopens its channel once
  `mise run start` re-enables the ingest user.

See [`docs/lessons.md`](docs/lessons.md) for what each part teaches.
