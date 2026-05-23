# Closure: Release — pipeline-restart-r1

> **Status:** Draft (template — populate when all TASKS.md tasks are [x] DONE)
> **Release ID:** pipeline-restart-r1
> **Owner:** product-engineer
> **Closed:** YYYY-MM-DD

---

## Summary

<!-- 1–3 paragraphs from the product owner's perspective describing what shipped. -->

## Tasks completed

| Task ID | Description | Final commit |
|---------|-------------|--------------|
| T-R1-01 | Remove dynamodb:Scan from ECS task role | `<sha>` |
| T-R1-02 | Replace IAM wildcard ARNs with explicit region+account | `<sha>` |
| T-R1-03 | Remove SSM Etherscan/Web3 access from Databricks cluster role | `<sha>` |
| T-R1-04 | Scope Lambda CloudWatch IAM ARN | `<sha>` |
| T-R1-05 | Set embed_credentials: false in all 4 dashboard bundles | `<sha>` |
| T-R1-06 | Pin dm-chain-utils==0.2.9 in all production artifacts | `<sha>` |
| T-R1-07 | Document LGPD PII classification in constitution.md | `<sha>` |
| T-R1-08 | Add build artifacts to .gitignore and clean git index | `<sha>` |
| T-R1-09 | Delete deprecated monolith bundle and pre-split source tree | `<sha>` |
| T-R1-10 | Pause DEV DLT trigger; start Docker Compose streaming stack | `<sha>` |
| T-R1-11 | Fix DEV trigger cron to 5-min; set pause_status: PAUSED | `<sha>` |
| T-R1-12 | Fix DynamoDB deadlock alert table reference | `<sha>` |
| T-R1-13 | Embed warehouse_id in all 4 dashboard bundle targets | `<sha>` |
| T-R1-14 | Fix 4 wrong Genie table FQNs | `<sha>` |
| T-R1-15 | Fix network-overview dashboard: remove non-existent table references | `<sha>` |
| T-R1-16 | Fix hot-contracts and gas-analytics dashboards to use Gold MVs | `<sha>` |
| T-R1-17 | Fix HML ingestion bucket name in DLT bundle config | `<sha>` |
| T-R1-18 | Remove lakehouse S3 folder prefixes (medallion naming violation) | `<sha>` |
| T-R1-19 | Promote from_address to expect_or_drop in DLT | `<sha>` |
| T-R1-20 | Refactor eth_canonical_blocks_index to bounded rolling window | `<sha>` |

---

## Validations

| Description | Command | Evidence |
|-------------|---------|----------|
| DEV Gold MV row count > 0 | `databricks sql execute --statement "SELECT count(*) FROM dev.g_apps.popular_contracts_ranking"` | `<stdout snippet>` |
| All 4 dashboards render (no empty widget) | Visual inspection in Databricks UI | `<sha or screenshot path>` |
| Genie NL query returns results | Submit NL query in Genie space | `<sha or screenshot path>` |
| P1 deadlock alert evaluates correctly | Manual trigger of alert_dynamodb_deadlock | `<sha or stdout>` |
| No dynamodb:Scan in ECS task role | `aws iam get-role-policy --role-name dm-chain-explorer-ecs-task-role --policy-name <name>` | `<stdout snippet>` |
| No wildcard *:* ARNs in IAM | `grep -r '\*:\*' services/prd/03_iam/` | empty output |
| dm-chain-utils pinned exactly | `grep 'dm-chain-utils' apps/docker/onchain-stream-txs/requirements.txt` | `dm-chain-utils==0.2.9` |
| No build/ directories in git | `git status` | clean |
| eth_canonical_blocks_index bounded window active | DLT run log review | `<sha>` |

---

## Drifts

<!-- Fill in for each place where reality diverged from PLAN.md during implementation. -->

<!-- Example:
### drift-iam-role-name
**Description:** IAM role name in production differed from the name used in PLAN.md.
**Resolution:** Updated Terraform var to match existing production resource.
**Memory updates:** specs/memory/aws-resources.html — IAM role name corrected.
-->

---

## Memory updates

<!-- CLOSURE gate: product-engineer is the ONLY agent that may write specs/memory/*.html.
     The following three memory HTML atoms MUST be created during this CLOSURE phase.
     See TASKS.md T-R1-CL-01 through T-R1-CL-03. -->

- [ ] **T-R1-CL-01** — `specs/memory/architecture.html` — create from `architecture.md`; update
  to reflect post-R1 operational state: ECS task role scoped, no IAM wildcards, DEV pipeline
  restart confirmed, canonical blocks index bounded window.

- [ ] **T-R1-CL-02** — `specs/memory/aws-resources.html` — create from `aws-resources.md`; update
  to reflect IAM fixes: removed dynamodb:Scan, scoped Kinesis/SQS/SSM ARNs, removed Databricks
  cluster SSM access, scoped Lambda CloudWatch ARN.

- [ ] **T-R1-CL-03** — `specs/memory/data-catalog.html` — create from `data-catalog.md`; update
  with corrected table FQNs (no stale `_fast` aliases), alert reference fix (logs_streaming),
  remove non-existent `dev.gold.blocks_hourly_summary` from any catalog entries.

Memory files NOT migrated in this CLOSURE (deferred to later releases):
- `specs/memory/tech-stack.md` — migration to HTML deferred to R2 CLOSURE (Kinesis/ECS changes pending).
- `specs/memory/constitution.md` — migration to HTML deferred to R4 CLOSURE (OQ-1 catalog name, OQ-3 parameterization must be resolved first).
- `specs/memory/product.md` — migration to HTML deferred to R4 CLOSURE (orphaned MV and alert threshold decisions fold in at R4).

After HTML atoms are written, move legacy Markdown atoms:
```bash
mkdir -p specs/_archive/legacy-memory/<UTC-timestamp>
git mv specs/memory/architecture.md specs/_archive/legacy-memory/<UTC-timestamp>/
git mv specs/memory/aws-resources.md specs/_archive/legacy-memory/<UTC-timestamp>/
git mv specs/memory/data-catalog.md specs/_archive/legacy-memory/<UTC-timestamp>/
```

---

## Backlog returns

<!-- Items discovered during implementation that did not fit this release. -->

---

## Archive decision

**MOVE** — after CLOSURE.md is complete and memory HTML atoms are written:

```bash
git mv specs/releases/pipeline-restart-r1 specs/_archive/releases/pipeline-restart-r1
```

Update `specs/releases/ACTIVE.md`:
```
release: cost-and-availability-r2
phase: TASKS
```
