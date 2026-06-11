# Backlog — CANDIDATE EPIC: Full-Platform Audit Remediation (2026-06-11)

> **Status:** CANDIDATE — NOT picked into any release.
> **Owner:** project-manager (sole backlog curator).
> **Created:** 2026-06-11
> **Source:** consolidated 4-agent audit `specs/audits/20260611T001412Z-cb56f84c/`
> (architecture-review, security-review, cicd-terraform-review, sdd-drift-audit).
> Totals: **5 CRITICAL / 17 HIGH / 28 MEDIUM / 20 LOW**, SDD scorecard 5.8/10,
> doctor [fail] 8 ERROR / 18 WARN.
> **Operator intent:** the repo was built by weak models; every architecture,
> security, and infra decision was re-reviewed zero-trust. This epic captures ALL
> remediation gaps. Maturation into releases follows `release-governance`
> (PM dispatch → product-engineer pick → mandatory grill → SPEC).
>
> Finding IDs reference the evidence reports in the audit dir. Do not re-derive —
> each report carries file:line evidence.

---

## WS-A — CI safety: stop the bleeding (CRITICAL)

| Item | Findings | Sev | Summary |
|---|---|---|---|
| A1 plan-visible gated applies | CI-C1 | CRIT | Approver must see the per-stack plan before PRD/HML apply; split env gate per stack or post plan artifact to the approval |
| A2 per-stack apply signal | CI-C2 | CRIT | Replace `grep`+`tail -1` over shared `$GITHUB_OUTPUT` in `deploy_env.sh:77` with per-stack step outputs; remove the silent `/dev/null` skip |
| A3 destroy-all concurrency group | CI-C3 | CRIT | `concurrency:` group + `cancel-in-progress: false` on `destroy_all_cloud_infra.yml` (it deletes the state bucket + lock table); also CI-M9 for auto-bump + drift workflows |
| A4 kill error masking | CI-H8, CI-M1, CI-M2 | HIGH | No `tee`/`tail` masking plan exit codes; purge `\|\| true` from teardown/test steps; full plan artifacts not `tail -N` |
| A5 timeouts everywhere | CI-H4 | HIGH | `timeout-minutes` on every job in all 7 workflows |
| A6 fmt/validate CI gate | CI-H1 | HIGH | `terraform fmt -check -recursive` + validate gate (15 files currently fail fmt) |
| A7 change-detection correctness | CI-H3, CI-M3 | HIGH/MED | Module-change → only dependent stacks; fix `HEAD~1` fallback misclassification |

## WS-B — Identity & secrets (HIGH security)

| Item | Findings | Sev | Summary |
|---|---|---|---|
| B1 purge Infura key logging | SEC-H-01 (CWE-532) | HIGH | Stop logging raw key at `4_mined_txs_crawler.py:66,107,114`; scrub/expire already-shipped logs in CloudWatch + `*-lakehouse/raw` + Databricks; rotate the key |
| B2 OIDC migration | SEC-H-02, SEC-I-01 (CWE-798) | HIGH | Replace static AWS keys with GitHub OIDC role-assumption in all 7 workflows; least-privilege roles per env; read-only role for PR plans |
| B3 PR-plan credential isolation | SEC-M-05 | MED | `plan_on_pr.yml` runs terraform on untrusted PR content with cloud creds — restrict to read-only role + require approval for fork PRs |
| B4 encryption at rest | SEC-M-01/M-02/M-04, ARCH-M9 | MED | Kinesis `encryption_type=NONE` → KMS; SQS SSE; CMK posture decision for DynamoDB/Firehose-S3 |
| B5 Databricks token in TF state | SEC-M-03 | MED | Bootstrap token persisted in state — move to short-lived auth / secret manager |
| B6 low-sev hardening batch | SEC-L-01..L-05 | LOW | SQS `Principal:*` allow policy, ECR MUTABLE+force_delete, ECS task hardening (root, rw fs), public-ip tasks, `.gitguardian.yml` blind spots |

## WS-C — Kill the split brains (CRITICAL architecture)

| Item | Findings | Sev | Summary |
|---|---|---|---|
| C1 retire stale PRD Databricks monolith | ARCH-C1 | CRIT | State surgery: confirm `05a`+`05b` own all resources, migrate `prevent_destroy`, destroy/abandon `services/prd/05_databricks` state `prd/databricks`, purge Makefile + `tf_validate_all.sh` references |
| C2 HML must validate PRD | ARCH-C2 | CRIT | Fix `dlt_ethereum` HML target `hml-raw` → `hml-lakehouse/raw/`; deploy HML DABs to the Terraform-provisioned MWS workspace, not the hardcoded shared dev workspace |
| C3 Makefile retirement | ARCH-H2, CI-L1..L5 | HIGH | The 23KB Makefile is a stale parallel control plane (broken targets, dead paths, drives the stale C1 stack) — reduce to thin dev-convenience wrappers over the same scripts CI uses, or delete |

## WS-D — Parameterize: one codepath per stack (HIGH)

| Item | Findings | Sev | Summary |
|---|---|---|---|
| D1 single stack tree + per-env tfvars | CI-H5/H6/H7, ARCH-H1, CI-M4/M5, CI-L7 | HIGH | Collapse dev/hml/prd copies of the same stack into one definition + tfvars/backend-config per env; PRD onto `services/modules/*`; backend/bucket/region/account out of hardcode |
| D2 reproducible providers | ARCH-H6, CI-H2, CI-M7 | HIGH | Commit `.terraform.lock.hcl`; one terraform + provider version floor repo-wide; `required_providers` in modules |
| D3 DABs config dedup | ARCH-M3, ARCH-M5 | MED | Shared bundle config across the 15 dabs apps (divergence already happened); delete or finish `genie_ethereum` scaffolding |
| D4 module interface hygiene | CI-M8, CI-M11 | MED/LOW | Variable descriptions/validation/typing; purge commented-out blocks |
| D5 availability-posture ADR | ARCH-H4, ARCH-M10 | HIGH/MED | Record (or change) single-AZ public subnet + FARGATE_SPOT + 1-shard Kinesis as an explicit cost ADR; document the desired_count-outside-terraform contract |

## WS-E — Capture-layer deprecation (supersession by dd-chain-capture)

| Item | Findings | Sev | Summary |
|---|---|---|---|
| E1 deprecation ADR | ARCH-H5 | HIGH | Formal ADR: capture layer (ECS+SQS+Kinesis+Firehose+DynamoDB) superseded by dd-chain-capture (VPS+Swarm+Kafka+Redis); S3 stays the integration boundary; define sunset criteria |
| E2 dead-code/infra removal wave | ARCH-H5, ARCH-M6, ARCH-M8, drift-04 | MED | Kafka-era argv in live ECS task defs, vestigial ABI cache + dead IAM grants, phantom REST API spec (SPEC+PLAN+TASKS, zero code), kafka/avro dead code |
| E3 dangling producer decision | DRIFT-1, ARCH-M8 | HIGH | `contracts_ingestion` Lambda writes `raw/batch/` that nothing ingests; ADR-005 Lambda-architecture union documented but never built — implement or descope + rewrite memory |

## WS-F — SDD/memory fidelity (current dadaia-workspace pattern)

| Item | Findings | Sev | Summary |
|---|---|---|---|
| F1 rewrite architecture.md to reality | ARCH-H3 (fidelity REJECT), ARCH-M1/M2/M4 | HIGH | Firehose paths, IAM naming, `-prd` suffixes, MWS-not-Free-Edition, desired_count=0 fleet, dev remote-state truth, HML lifecycle truth, catalog name — product-engineer, DEFINITION/CLOSURE phase only |
| F2 data-catalog/ADR-005 truth | DRIFT-1 | HIGH | Memory documents nonexistent `popular_contracts_txs` union path — align with E3 outcome |
| F3 close fixed bugs + doctor errors | DRIFT-4, doctor 8E/18W | MED | 7 of 8 `specs/bugs/` fixed-but-Open → close with evidence; add missing `session_id:` frontmatter (all 8 doctor ERRORs) |
| F4 retire `specs/domains/` legacy tree | DRIFT-5 / open task T-R5-F1 | MED | 8 files, non-canonical vs dadaia-workspace pattern — archive or fold into memory atoms |
| F5 wire streaming tests into CI | DRIFT-5 | MED | 71 streaming-job unit tests exist but CI runs only `utils/tests/unit/` (`deploy_all_dm_applications.yml:154`); also CI-M6 dm-chain-utils pin mismatch |
| F6 quality-assurance.md atom | DRIFT-5 | LOW | Currently a stub — document the real test pyramid + gates |
| F7 capture supersession in memory | ARCH-H5 | MED | Memory nowhere mentions dd-chain-capture supersession — add after E1 ADR |

## WS-G — Repo hygiene

| Item | Findings | Sev | Summary |
|---|---|---|---|
| G1 working-tree pollution | ARCH-M7, CI-L6 | MED | `apps/dabs/**/.databricks/` bundle state, stray `.terraform/`, duplicate test trees — gitignore + clean recipe (`.hypothesis/` already removed post-audit) |
| G2 branch-model decision | CI-M10 | MED | `prd-create-tag` tags `master` while deploys run from `develop` — pick and document one branch model |

---

## Suggested maturation order

WS-A (CI safety) → WS-B1/B2 (secrets) → WS-C (split brains) → WS-D (parameterize)
→ WS-E (deprecation) → WS-F (memory truth) → WS-G. WS-A+B1 are small and
self-contained enough for a first patch release; WS-D is the big structural one and
dissolves ~⅓ of all findings; WS-F6/F1/F2 must FOLLOW the architectural decisions
(E1/E3/D5) or memory will be rewritten twice.

**Mandatory before any SPEC:** `dadaia-grill-me` session on the picked subset
(release-governance).
