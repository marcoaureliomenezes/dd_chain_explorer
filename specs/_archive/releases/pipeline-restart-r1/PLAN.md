# PLAN: pipeline-restart-r1

**Status:** Aprovado
**Release:** pipeline-restart-r1
**Owner:** product-engineer
**Source:** SPEC.md (this release) + PM mediation matrix Part 2

---

## Strategy

Three parallel work-packages run in dependency order. Security fixes and repo hygiene are
independent and can start immediately. The DEV pipeline restart is the critical path gate
for all serving-layer fixes — dashboards cannot be validated until the pipeline produces data.

```
Work-Package A: Security + IAM (devops-engineer) — no dependencies
Work-Package B: Repo hygiene + bundle fixes (software-engineer-python) — no dependencies
Work-Package C: DEV pipeline restart (devops-engineer) — no dependencies
                 └── Work-Package D: DLT + serving layer fixes (data-engineer + data-analyst)
                                     └── starts after DEV streaming data confirmed in S3
Work-Package E: DLT pipeline code fixes (data-engineer) — independent of C/D
```

---

## Work-Package A: IAM + Security Hardening

**Owner:** devops-engineer
**Evidence references:** `iam/main.tf:62–92`, `iam/main.tf:104–108`, `iam/main.tf:384–395`,
`iam/main.tf:438–442`

### A1 — ECS task role over-privilege (ISSUE-008, ISSUE-009, ISSUE-010, ISSUE-023)

Four IAM fixes in the same Terraform module. Apply as a single `terraform apply` on
`services/prd/03_iam/`:

1. Remove `dynamodb:Scan`; replace with `GetItem`, `PutItem`, `DeleteItem`, `UpdateItem`
   scoped to single-table ARN (ISSUE-008).
2. Replace all `arn:aws:*:*:*` ARN wildcards with
   `arn:aws:kinesis:${var.region}:${var.account_id}:stream/${var.name_prefix}-*` pattern,
   and analogous for SQS, SSM (ISSUE-009).
3. Remove SSM `etherscan-api-keys` and `web3-api-keys` from Databricks cluster IAM role
   (ISSUE-010).
4. Scope Lambda CloudWatch IAM to
   `arn:aws:logs:${var.region}:${var.account_id}:log-group:/aws/lambda/${var.name_prefix}-*`
   (ISSUE-023).

**BLOCKED-BY-OPERATOR-DECISION: OQ-2** — DEV vs HML restart order does not block A1.
IAM changes apply independently.

### A2 — Dashboard credential embedding (ISSUE-020)

Set `embed_credentials: false` in all 4 dashboard bundle YAMLs:
`dashboard_*/resources/dashboards/*.yml:5`.
Re-deploy dashboards after warehouse_id is fixed (coordinate with Work-Package D).

### A3 — dm-chain-utils version pinning (ISSUE-021)

Pin `dm-chain-utils==0.2.9` in:
- `apps/docker/onchain-stream-txs/requirements.txt`
- `apps/lambda/contracts_ingestion/requirements.txt`
- `apps/lambda/gold_to_dynamodb/requirements.txt`

Add CI validation step to verify pinned version matches `VERSION` file.

### A4 — LGPD PII classification (ISSUE-022)

Add a "Data Classification" section to `specs/memory/constitution.md` stating:
Ethereum addresses are pseudo-anonymous public data per LGPD Art. 7 VI. No UC column masking
required until KYC-linked addresses are introduced.

---

## Work-Package B: Repository Hygiene

**Owner:** software-engineer-python
**Evidence:** `apps/dabs/*/src/*/build/` (DE-Q-001), `apps/dabs/_MONOLITH_DEPRECATED.databricks.yml`

### B1 — git artifact cleanup (ISSUE-033)

1. Add to root `.gitignore`:
   ```
   build/
   *.egg-info/
   dist/
   ```
2. Run: `git rm -r --cached apps/dabs/*/src/*/build/`
3. Commit: `chore(deps): remove build artifacts from git index`

### B2 — Deprecated bundle removal (ISSUE-034)

1. Verify no active `databricks.yml` references `apps/dabs/src/` path.
2. Delete `apps/dabs/_MONOLITH_DEPRECATED.databricks.yml`.
3. Remove pre-split source tree if confirmed unreferenced.
4. Commit: `chore(dabs): remove deprecated monolith bundle and pre-split sources`

---

## Work-Package C: DEV Pipeline Restart

**Owner:** devops-engineer
**Evidence:** CRIT-DBX-001, pipeline `be2bcafd`, NFR-DE-003

### C1 — Pause DEV trigger and start streaming stack (ISSUE-001)

BLOCKED-BY-OPERATOR-DECISION: OQ-2 (confirm DEV-first — default assumed).

Steps:
1. Pause job `dm-trigger-all-dlts` in DEV Databricks workspace:
   `databricks jobs update --json '{"pause_status":"PAUSED"}' --job-id <id>`
2. Start Docker Compose: `make deploy_dev_stream`
3. Confirm S3 Bronze data appears in `dm-chain-explorer-dev-ingestion/raw/mainnet-*/`
4. Resume `dm-trigger-all-dlts` only after S3 data confirmed.

### C2 — DEV trigger schedule fix (ISSUE-012)

Fix cron schedule from hourly to 5-min in `dlt_ethereum/databricks.yml` (DEV target):
```yaml
schedule:
  quartz_cron_expression: "0 */5 * * * ?"
  pause_status: PAUSED
```
Validate NFR-DE-003 compliance.

---

## Work-Package D: Serving Layer Fixes

**Owner:** data-analyst (dashboards, Genie, alerts), data-engineer (DLT config)
**Dependency:** Work-Package C must complete (S3 data confirmed) before serving-layer fixes
can be validated.

### D1 — Alert table reference fix (ISSUE-002)

File: `apps/dabs/alert_dynamodb_deadlock/resources/alert_dynamodb_deadlock.yml:19`
Change query table from `s_logs.apps_logs_fast` to `s_logs.logs_streaming`.
Verify message predicate matches actual structured log output.
Upgrade Databricks CLI if `alerts` resource type requires newer version.

### D2 — Dashboard warehouse_id (ISSUE-004)

1. Run `databricks warehouses list -o json` per target (dev, hml, prod).
2. Embed correct Starter warehouse ID in all 6 bundle target YAMLs:
   `dashboard_*/databricks.yml:8` (4 dashboards × 2 relevant targets).
3. Deploy: `make dabs_deploy_dev` and validate each dashboard renders.

### D3 — Genie FQN fix (ISSUE-005)

File: `apps/dabs/genie_ethereum/genie_ethereum.yml:19–37`
Four FQN corrections:
- `transactions_fast` → `{catalog}.s_apps.transactions_ethereum`
- `blocks_fast` → `{catalog}.s_apps.eth_blocks`
- `{catalog}.s_apps.popular_contracts_ranking` → `{catalog}.g_apps.popular_contracts_ranking`
- `{catalog}.s_apps.transactions_lambda` → `{catalog}.g_apps.transactions_lambda`

Upgrade Databricks CLI for `genie_spaces` resource type if required.

### D4 — Network overview dashboard queries (ISSUE-006)

File: `apps/dabs/dashboard_network_overview/resources/dashboards/01_network_overview.lvdash.json`
Rewrite 3 dataset queries:
- Remove hardcoded `dev.gold.blocks_hourly_summary` references
- Use `g_network.network_metrics_hourly` and `g_network.block_production_health`
- Use DEV catalog prefix for current target (full parameterization is OQ-3, deferred to R4)

### D5 — Hot contracts + gas analytics dashboard (ISSUE-007)

Files: `02_hot_contracts.lvdash.json`, `03_gas_analytics.lvdash.json`
- Redirect `s_apps.popular_contracts_ranking` queries to `g_apps.popular_contracts_ranking`
- Replace inline Silver percentile computation with `g_apps.gas_price_distribution_hourly`

---

## Work-Package E: DLT Pipeline Code Fixes

**Owner:** data-engineer
**Files:** `apps/dabs/dlt_ethereum/src/*/ethereum_pipeline.py`, `databricks.yml`

### E1 — HML ingestion bucket fix (ISSUE-014)

File: `apps/dabs/dlt_ethereum/databricks.yml:46`
Change `ingestion_s3_bucket` for HML target from `"dm-chain-explorer-hml-lakehouse"` to
`"dm-chain-explorer-hml-raw"`.

### E2 — S3 lakehouse folder prefixes (ISSUE-029)

File: `services/prd/04_peripherals/peripherals.tf:50–51`
Remove: `folder_prefixes = ["bronze","silver","gold"]`
Delete `.keep` placeholder objects from `dm-chain-explorer-lakehouse` bucket.

### E3 — from_address validation promotion (ISSUE-030)

File: `ethereum_pipeline.py:208–209`
Change `expect` → `expect_or_drop` for `from_address` validation.
Retain `expect` for `to_address` (NULL is valid for contract deploys).

### E4 — eth_canonical_blocks_index bounded window (ISSUE-003)

File: `ethereum_pipeline.py:486–505`
Refactor O(N^2) cross-join to bounded rolling window:
- Keep last 1,000 blocks in the window
- Mark blocks older than window as permanently `canonical`
- Validate with DEV DLT run after C1 completes

This is a pre-launch scalability gate. Must complete before any PRD restart.

---

## Architecture Decisions (this release)

- **IAM scoping** — all ARNs now use `${var.region}:${var.account_id}` pattern for
  environment isolation. This is a backward-compatible change; existing resources unaffected.
- **Dashboard warehouse_id** — embedded per target, not parameterized. Full parameterization
  blocked on OQ-3; current approach matches the `${var.catalog}` bundle variable pattern.
- **from_address as expect_or_drop** — records with invalid `from_address` are dropped at Bronze
  ingest rather than propagated to Gold with warning flags. Aligns with constitution Section 10
  (data quality invariant).
- **Bounded canonical blocks window** — 1,000 blocks covers ~3.3 hours at current Ethereum
  block rate (12s/block). This is sufficient for chain-reorg detection (reorgs >6 blocks are
  extremely rare). Older blocks accumulate as canonical.

## BLOCKED-BY-OPERATOR-DECISION Items

| OQ | Impact | Default |
|----|--------|---------|
| OQ-2 | Restart target: DEV or HML first? | DEV-first (this plan) |

No other blocked items in this release. All security fixes proceed without operator input.

## Validation Plan

After all work-packages complete:

1. `make deploy_dev_stream` — Docker Compose running, verify with `docker compose ps`
2. Confirm S3 Bronze data: `aws s3 ls s3://dm-chain-explorer-dev-ingestion/raw/ --recursive | head -5`
3. `make dabs_run_trigger_all` — trigger DLT pipelines
4. Check Gold MV row count: SQL `SELECT count(*) FROM dev.g_apps.popular_contracts_ranking`
5. Validate each dashboard renders in Databricks UI
6. Test Genie: submit one natural language query, verify no table-not-found error
7. Trigger `alert_dynamodb_deadlock` manually; verify it queries `s_logs.logs_streaming`
8. IAM policy review: `aws iam get-role-policy --role-name dm-chain-explorer-ecs-task-role`
9. `git status` — confirm no `build/` directories tracked
