# Closure: Release — pipeline-restart-r1

> **Status:** Aprovado
> **Release ID:** pipeline-restart-r1
> **Owner:** product-engineer
> **Closed:** 2026-05-23

---

## Summary

Release pipeline-restart-r1 delivered 20 tasks spanning four work-packages: IAM and security hardening, repository hygiene, DEV pipeline restart, and serving-layer fixes plus DLT code improvements. On the security front, the ECS task role was stripped of `dynamodb:Scan`, `Query`, `BatchGetItem`, `BatchWriteItem`, and `DescribeTable` — leaving only the four write/read primitives actually required — and all wildcard ARNs (`*:*`) in `services/prd/03_iam/iam.tf` were replaced with explicit `${region}:${account_id}` patterns. Databricks cluster access to SSM was removed, Lambda CloudWatch permissions were scoped, `dm-chain-utils` was pinned to `==0.2.9` across all production artifacts, and `embed_credentials: false` was confirmed in all four dashboard bundles. LGPD PII classification for Ethereum addresses was documented in the constitution.

The serving layer was fully repaired: all four Lakeview dashboards (Network Overview, Gas Analytics, Hot Contracts, API Health) were fixed and deployed to DEV as ACTIVE, with the root cause being a combination of stale table FQN aliases (`_fast` suffixes), missing `warehouse_id` embeddings, column name mismatches (`type_transaction` versus `tx_type_semantic`), and Databricks renderer incompatibility with widget `version:2` — resolved by upgrading all broken chart widgets to `version:3`. The DynamoDB deadlock alert was fixed to reference `s_logs.logs_streaming` rather than a non-existent table. The `eth_canonical_blocks_index` Silver MV was refactored from a full-table O(N^2) self-join to a bounded rolling window of 1,000 blocks (`_CANONICAL_WINDOW_BLOCKS=1_000`), eliminating the scan warning in DLT runs.

PRD infrastructure — S3 buckets (`dm-chain-explorer-raw-data`, `dm-chain-explorer-lakehouse`), SQS queues, IAM roles, and Lambda functions (`gold_to_dynamodb`, `contracts_ingestion`) — was applied fresh via Terraform on 2026-05-23 (had never been provisioned before). The DEV DLT trigger was paused (`PAUSED`) and the Docker Compose streaming stack brought up with 12 containers running, confirming the capture layer is healthy and ready for the next data-flow validation cycle.

---

## Tasks completed

| Task ID | Description | Final commit |
|---------|-------------|--------------|
| T-R1-01 | Remove dynamodb:Scan from ECS task role | `60c71c7` |
| T-R1-02 | Replace IAM wildcard ARNs with explicit region+account | `60c71c7` |
| T-R1-03 | Remove SSM Etherscan/Web3 access from Databricks cluster role | `60c71c7` |
| T-R1-04 | Scope Lambda CloudWatch IAM ARN | `60c71c7` |
| T-R1-05 | Set embed_credentials: false in all 4 dashboard bundles | `c70c588` |
| T-R1-06 | Pin dm-chain-utils==0.2.9 in all production artifacts | `d9de6c9` |
| T-R1-07 | Document LGPD PII classification in constitution.md | `d9de6c9` |
| T-R1-08 | Add build artifacts to .gitignore and clean git index | `27cfa65` |
| T-R1-09 | Delete deprecated monolith bundle and pre-split source tree | `67f8faf` |
| T-R1-10 | Pause DEV DLT trigger; start Docker Compose streaming stack | `00a47a9` |
| T-R1-11 | Fix DEV trigger cron to 5-min; set pause_status: PAUSED | `00a47a9` |
| T-R1-12 | Fix DynamoDB deadlock alert table reference | `04194d3` |
| T-R1-13 | Embed warehouse_id in all 4 dashboard bundle targets | `04194d3` |
| T-R1-14 | Fix 4 wrong Genie table FQNs | `04194d3` |
| T-R1-15 | Fix network-overview dashboard: remove non-existent table references | `3ab70dd` |
| T-R1-16 | Fix hot-contracts and gas-analytics dashboards to use Gold MVs | `3ab70dd` |
| T-R1-17 | Fix HML ingestion bucket name in DLT bundle config | `444a814` |
| T-R1-18 | Remove lakehouse S3 folder prefixes (medallion naming violation) | `60c71c7` |
| T-R1-19 | Promote from_address to expect_or_drop in DLT | `8adab6e` |
| T-R1-20 | Refactor eth_canonical_blocks_index to bounded rolling window | `8c285ab` |

---

## Validations

| Description | Command | Evidence |
|-------------|---------|----------|
| No dynamodb:Scan in ECS task role | `aws iam get-role-policy --role-name dm-chain-explorer-ecs-task-role --policy-name dm-ecs-task-permissions` | Actions: DeleteItem, GetItem, PutItem, UpdateItem only — Scan, Query, BatchGetItem, BatchWriteItem, DescribeTable absent |
| No wildcard ARNs in IAM | `grep -r '\*:\*' services/prd/03_iam/` | Empty output — all ARNs use `${var.region}:${account_id}` |
| dm-chain-utils pinned exactly | `grep 'dm-chain-utils' apps/docker/onchain-stream-txs/requirements.txt` | `dm-chain-utils==0.2.9` |
| No Databricks SSM access | IAM policy inspection — `dm-databricks-cluster-role` | SSMAccess statement absent from `databricks_cluster_permissions` policy |
| Lambda CloudWatch scoped | `grep -A5 'logs:CreateLogGroup' services/prd/06_lambda/lambda.tf` | ARN: `arn:aws:logs:${var.aws_region}:${account_id}:log-group:/aws/lambda/${local.name_prefix}-*` |
| DEV DLT trigger paused | Databricks UI / DABs deploy output | `[dev] dm-trigger-all-dlts` PAUSED; Docker stack UP 12 containers |
| Network Overview dashboard ACTIVE | DABs deploy log | `id=01f130f640de104ba0ffb93e4b0a32c8`, status ACTIVE — counters: 2411 blocks, 396.3 avg tx, 1.6 avg gas; 4 line charts rendering |
| Gas Analytics dashboard ACTIVE | DABs deploy log | `id=01f130f64d4d1d5ca50457cfafdc82ad`, status ACTIVE — bar charts: contract_interaction ~710K, peer_to_peer ~96K |
| Hot Contracts dashboard ACTIVE | DABs deploy log | `id=01f130f6471412f29cb443ac92bcce76`, status ACTIVE — widgets rendering; 0 rows expected (pipeline paused) |
| API Health dashboard ACTIVE | DABs deploy log | `id=01f130f65385152280abbea7b5017f19`, status ACTIVE — Etherscan 6 rows, Web3 9 rows |
| deadlock alert query resolves | `databricks sql execute --statement "SELECT ..."` against `dev.s_logs.logs_streaming` | SUCCEEDED, 0 deadlock_events, no table-not-found |
| eth_canonical_blocks_index bounded window | Code review `ethereum_pipeline.py:491–573` | `_CANONICAL_WINDOW_BLOCKS=1_000` — outside_window/window_blocks/parent_refs/inside_window CTEs; no full-table self-join |
| popular_contracts_ranking 0 rows (expected) | `databricks sql execute --statement "SELECT count(*) FROM dev.g_apps.popular_contracts_ranking"` | 0 rows — DEV pipeline paused by design |
| PRD infrastructure applied | `terraform apply services/prd/04_peripherals` + `services/prd/03_iam` + `services/prd/06_lambda` | 40 added (peripherals), 2 changed 0 destroyed (IAM), 12 added (Lambda) |
| No build/ in git index | `git status` | Clean — no tracked build/ or *.egg-info/ directories |

---

## Drifts

### drift-iam-module-path

**Description:** T-R1-01 through T-R1-04 and T-R1-18 were initially committed to `services/modules/iam/main.tf` — a module path that exists in the repository but is not consumed by any Terraform root module in the workspace. The actual IAM root module used by the PRD environment is `services/prd/03_iam/iam.tf`.

**Resolution:** The fix was re-applied directly to `services/prd/03_iam/iam.tf` on 2026-05-23. The unused module path was left as-is (not deleted) to avoid scope creep; it may be cleaned up in a future hygiene release. Commit `60c71c7` captures the corrected state.

**Memory updates:** `specs/memory/aws-resources.html` — IAM roles section updated to reflect scoped permissions; Terraform state paths table updated to show PRD peripherals applied fresh.

### drift-gas-analytics-column-mismatches

**Description:** T-R1-16 required two re-fix passes beyond the initial implementation. The first pass identified that `type_transaction` is not a valid column in `g_apps.ethereum_gas_consume` — the correct column is `tx_type_semantic`. The second pass identified that `gas_hourly` was applying `DATE_TRUNC` to `tx_timestamp`, which is a STRING column, causing a cast error; this was resolved by grouping by `block_number` instead. A third pass was required to upgrade all broken chart widgets from `version:2` (unrecognized by Databricks renderer) to `version:3`.

**Resolution:** All three passes committed under `3ab70dd`. SQL validation confirmed both queries SUCCEEDED with real data before final dashboard deploy. The widget v3 upgrade was applied uniformly across all four dashboards (not only gas_analytics).

**Memory updates:** `specs/memory/data-catalog.html` — `g_apps.ethereum_gas_consume` entry updated to document `tx_type_semantic` as the canonical column name.

### drift-prd-infrastructure-first-apply

**Description:** PRD infrastructure (S3, SQS, Firehose, Kinesis, DynamoDB via `04_peripherals`; IAM roles via `03_iam`; Lambda functions via `06_lambda`) had never been applied via Terraform before this release. The PLAN assumed resources were already provisioned. The `terraform apply` for `04_peripherals` added 40 resources fresh, `03_iam` modified 2 (post-IAM-fix, first real apply), and `06_lambda` added 12.

**Resolution:** All resources applied successfully on 2026-05-23. PRD infrastructure is now live. This drift did not require any memory update beyond what was already captured in the IAM and S3 sections of `specs/memory/aws-resources.html`.

**Memory updates:** `specs/memory/aws-resources.html` — SQS PRD queues, Lambda PRD functions, and IAM roles sections now reflect provisioned state.

---

## Memory updates

- `specs/memory/architecture.html` — created fresh from `architecture.md`; updated to reflect post-R1 operational state: ECS task role scoped (no Scan/wildcard), DEV pipeline PAUSED, Docker Compose capture stack UP 12 containers, `eth_canonical_blocks_index` uses bounded 1,000-block rolling window, all 4 DEV dashboards ACTIVE.
- `specs/memory/aws-resources.html` — created fresh from `aws-resources.md`; updated to reflect: IAM roles have no `dynamodb:Scan`, no wildcard ARNs, no Databricks SSM access, Lambda CloudWatch scoped; PRD infrastructure provisioned (S3, SQS, IAM, Lambda) first time 2026-05-23.
- `specs/memory/data-catalog.html` — created fresh from `data-catalog.md`; updated with corrected FQNs (no `_fast` aliases in Genie or dashboards), `s_logs.logs_streaming` as the alert reference, `tx_type_semantic` canonical column in `ethereum_gas_consume`, note that `popular_contracts_ranking` is 0 rows because DEV pipeline is paused.

Memory files NOT migrated in this CLOSURE (deferred to later releases):
- `specs/memory/tech-stack.md` — migration to HTML deferred to R2 CLOSURE (Kinesis/ECS changes pending).
- `specs/memory/constitution.md` — migration to HTML deferred to R4 CLOSURE (OQ-1 catalog name, OQ-3 parameterization must be resolved first).
- `specs/memory/product.md` — migration to HTML deferred to R4 CLOSURE (orphaned MV and alert threshold decisions fold in at R4).

Legacy markdown atoms migrated to archive:
```bash
mkdir -p specs/_archive/legacy-memory/2026-05-23
git mv specs/memory/architecture.md specs/_archive/legacy-memory/2026-05-23/
git mv specs/memory/aws-resources.md specs/_archive/legacy-memory/2026-05-23/
git mv specs/memory/data-catalog.md specs/_archive/legacy-memory/2026-05-23/
```

---

## Backlog returns

- `backlog/candidates.md` ← Remove unused `services/modules/iam/main.tf` module path (hygiene; not consumed by any root module)
- `backlog/candidates.md` ← Validate PRD streaming pipeline end-to-end after ECS task role IAM scoping (T-R1-01/02 changes may surface permission gaps at runtime)
- `backlog/ideas.md` ← Investigate `genie_spaces` DABs provider support (v1.88.0 does not manage Genie space creation; Genie space FQN correctness is validated via SQL only)

---

## CLOSURE tasks

- [x] T-R1-CL-01 — `specs/memory/architecture.html` created and reflects post-R1 architecture.
- [x] T-R1-CL-02 — `specs/memory/aws-resources.html` created and reflects post-R1 IAM/infra state.
- [x] T-R1-CL-03 — `specs/memory/data-catalog.html` created with corrected FQNs and schema notes.

---

## Archive decision

**MOVE** — release directory moved to `specs/_archive/releases/pipeline-restart-r1/` via `git mv`.

```bash
mkdir -p specs/_archive/releases
git mv specs/releases/pipeline-restart-r1 specs/_archive/releases/pipeline-restart-r1
```

`specs/releases/ACTIVE.md` updated to:
```
release: capture-decoupling-r5
phase: TASKS
```
