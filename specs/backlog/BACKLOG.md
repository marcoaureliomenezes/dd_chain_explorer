# Backlog — dd-chain-explorer

> Single-source backlog (`dd-backlog-definition` §2): `## ACTIVE` holds live candidates,
> `## LEDGER` holds one line per closed item. Nothing is deleted — an item leaves ACTIVE only
> by gaining a LEDGER line. Curated by `project-manager`. Folded on 2026-08-23 from the seven
> legacy loose files now under `specs/backlog/_archive/` (read-only history).
>
> **Intake provenance (2026-08-23).** Every `v050-*` entry below is an intake-report item from
> the full audit `specs/audits/20260823T145726Z-4db47555/consolidated-audit.md` (DRIFT-01..31),
> merged with the still-live, in-scope findings of the undispositioned audit
> `specs/audits/20260611T001412Z-cb56f84c/`. The operator directive of 2026-08-23 ("close v0.4.0,
> work all clear points found and fix them, run another audit at the end; scope = Terraform
> infra, GitHub Actions CI, Databricks artifacts; capture moved to dd-chain-capture") is the
> ratification — these entries are **approved intake**, the candidate set for the single
> remediation release **v0.5.0**. Intake report:
> `.dadaia/reports/dd-chain-explorer/project-manager/2026-08-23T152638Z-intake-report-audit-20260823.md`.
> Proposed disposition per entry is stated in its Description (`pick v0.5.0` / `defer`).
> **Purge-on-pick (2026-08-23).** The 18 `v050-*` entries picked by release v0.5.0 left ACTIVE in
> the commit that created `specs/releases/v0.5.0/SPEC.md` (its `**Consumes:**` line is the provenance,
> together with the intake report above). LEDGER lines are added at CLOSURE's disposition sweep.
> The 7 deferred entries remain ACTIVE.

## ACTIVE

### capture-ecr-state-and-kms-ownership-transfer
- **Title:** Move the dd-chain-capture `capture/ecr` Terraform state + KMS key out of this repo's state bucket (or document the hosting)
- **Opened:** 2026-08-23
- **Status:** candidate
- **Description:** DRIFT-23 (MEDIUM, cross-project). `capture/ecr` state (dd-chain-capture ECR + RolesAnywhere + KMS, 11 resources) lives in this repo's state bucket with no source here; KMS `alias/dd-chain-capture-ssm` protects 0 params (≈US$ 1/mo); 2 ECR repos empty; scraper role last assumed 2026-07-12. Owner of the resources is dd-chain-capture. Scope: live-ops. Owner: operator + dd-chain-capture context. **Proposed: defer/route** — route to dd-chain-capture for the state move; the only v0.5.0 action here is documenting the hosted state key in `aws-resources.md` (folded into the memory residual).
- **Provenance:** intake-report item DRIFT-23 (approved 2026-08-23, operator directive — routed)
- **Intents:**
```yaml
- subject:
    kind: doc
    ref: memory/product/aws-resources.md#terraform-state-keys
  change: The capture/ecr state key is either listed as hosted-for-dd-chain-capture (with owner) or gone from this bucket after the move.
```

### terraform-single-stack-tree-per-env-tfvars
- **Title:** Collapse dev/hml/prd stack copies into one definition + per-env tfvars/backend-config; DABs shared bundle config
- **Opened:** 2026-06-11
- **Status:** candidate
- **Description:** Legacy WS-D/D1 (CI-H5/H6/H7, ARCH-H1, CI-M4/M5, CI-L7), D3 (ARCH-M3/M5 shared bundle config across 15 DABs apps), D4 (CI-M8/M11 variable descriptions/validation, commented-out blocks). Structural refactor of all 24 stacks onto `services/modules/*` with backend/bucket/region/account out of hard-coded literals. Scope: infra-terraform + databricks-artifacts. Owner: software-architect (design) → software-engineer. **Proposed: defer** to the release after v0.5.0 — it is a restructuring, not a drift fix; it needs the HML fate decision and the dead-IaC purge first, otherwise it refactors stacks that are about to be deleted.
- **Provenance:** intake-report item 2026-06-11 WS-D/D1/D3/D4 (approved 2026-08-23 as deferred)
- **Intents:**
```yaml
- subject:
    kind: doc
    ref: memory/tech-stack.md#aws-surface
  change: One stack definition per concern with per-environment tfvars/backend-config; DEV/HML/PRD differ only by variables.
- subject:
    kind: doc
    ref: memory/architecture.md#contratos-entre-módulos
  change: Module interface contract (typed, described, validated variables; no commented-out blocks) and a shared DABs bundle include consumed by every app.
```

### dlt-ethereum-data-quality-enhancements
- **Title:** DLT ethereum correctness: event-time windows, Auto Loader schema evolution, drop orphaned Gold MVs, bounded-window validation
- **Opened:** 2026-06-10
- **Status:** candidate
- **Description:** Legacy CAND-R3-01 (`current_timestamp()` in Gold MV window filters → event-time), CAND-R3-02 (`schemaEvolutionMode: addNewColumns`), CAND-R3-03 (validate `eth_canonical_blocks_index` bounded window under ≥7 d load), CAND-R3-05 (drop orphaned `contract_deploy_metrics_hourly` + `contract_method_activity`, OQ-4). Scope: databricks-artifacts. Owner: software-engineer. **Proposed: defer** — the platform is dry (no raw data since 2026-05-23); these need flowing data to validate and are enhancements, not drift. Re-pick once the dd-chain-capture feed is live.
- **Provenance:** intake-report item legacy CAND-R3-01/02/03/05 (approved 2026-08-23 as deferred)
- **Intents:**
```yaml
- subject:
    kind: code
    ref: apps/dabs/dlt_ethereum/src/streaming/ethereum_pipeline.py#_auto_loader_json
  change: Add schemaEvolutionMode addNewColumns and a schema-version marker to the Auto Loader reader.
- subject:
    kind: code
    ref: apps/dabs/dlt_ethereum/src/streaming/ethereum_pipeline.py#gold_contract_deploy_metrics_hourly
  change: Drop the orphaned Gold MV (OQ-4 decision) or justify keeping it.
- subject:
    kind: code
    ref: apps/dabs/dlt_ethereum/src/streaming/ethereum_pipeline.py#gold_contract_method_activity
  change: Drop the orphaned Gold MV (OQ-4 decision) or justify keeping it.
- subject:
    kind: code
    ref: apps/dabs/dlt_ethereum/src/streaming/ethereum_pipeline.py#silver_eth_canonical_blocks_index
  change: Validate the bounded window under at least 7 days of live load and record the sign-off; Gold windows use event time, not current_timestamp().
```

### dashboards-analytics-enrichment
- **Title:** Dashboards: freshness KPI tile, date-range filter, alert-threshold reference line; analyst GRANT DDL + column COMMENTs
- **Opened:** 2026-05-22
- **Status:** candidate
- **Description:** Legacy CAND-R4-03 (freshness KPI on all 4 dashboards), CAND-R4-05 (date-range filter widget), LOW-3 (alert threshold reference line), CAND-R4-04 (analyst GRANT DDL for Gold schemas), CAND-R4-06 (`COMMENT ON COLUMN` for Gold MV columns). Scope: databricks-artifacts. Owner: software-engineer. **Proposed: defer** — serving enhancements on a platform with no fresh data; pick after the feed is live and v050-databricks-bundle-config-hardening has parameterized the dashboards.
- **Provenance:** intake-report item legacy CAND-R4-03/04/05/06 + LOW-3 (approved 2026-08-23 as deferred)
- **Intents:**
```yaml
- subject:
    kind: doc
    ref: memory/product/serving-layer.md#diferencial
  change: Each dashboard carries a freshness KPI tile, a date-range filter where applicable, and alert-threshold reference lines.
- subject:
    kind: code
    ref: apps/dabs/job_ddl_setup/src/dd_chain_explorer/ddl/setup_ddl.py#main
  change: DDL adds analyst GRANTs on every Gold schema and COMMENT ON COLUMN for every Gold MV column.
```

### encryption-at-rest-posture-decision
- **Title:** Encryption-at-rest posture: CMK vs AWS-managed for DynamoDB/S3, KMS bill audit, Public-Default policy record
- **Opened:** 2026-05-22
- **Status:** candidate
- **Description:** Legacy CAND-R2-08 (KMS bill audit + Public-Default Encryption policy, OQ-NEW-1) and the surviving half of WS-B/B4 (SEC-M-04 CMK posture for DynamoDB / S3 — the Kinesis/SQS halves are obsolete). Scope: infra-terraform. Owner: security-reviewer (posture) → software-engineer. **Proposed: defer** — no new data at rest is being written; decide with the re-feed contract; the DynamoDB table may itself be removed by v050-contracts-ingestion-schedule-and-lambda-path-decision.
- **Provenance:** intake-report item legacy CAND-R2-08 + WS-B/B4 residual (approved 2026-08-23 as deferred)
- **Intents:**
```yaml
- subject:
    kind: doc
    ref: memory/architecture.md#adr-003-single-table-dynamodb-design
  change: Record the encryption-at-rest decision (CMK or AWS-managed) for the table — if the table survives — and the Public-Default policy as an ADR.
```

### s3-raw-lifecycle-intelligent-tiering
- **Title:** S3 lifecycle on the `raw/` prefix (INTELLIGENT_TIERING) instead of STANDARD_IA/GLACIER on `""`
- **Opened:** 2026-06-10
- **Status:** candidate
- **Description:** Legacy CAND-R2-04 (T-R2-04 / ISSUE-024). `module.s3_raw` applies STANDARD_IA/GLACIER on the `""` prefix, not IT on `raw/`. Scope: infra-terraform. Owner: software-engineer. **Proposed: defer** — cost optimization on a bucket that is currently empty; pick once dd-chain-capture delivers and the prefix layout (`year=/month=/…`) is confirmed.
- **Provenance:** intake-report item legacy CAND-R2-04 (approved 2026-08-23 as deferred)
- **Intents:**
```yaml
- subject:
    kind: doc
    ref: memory/product/aws-resources.md#s3-buckets
  change: Raw bucket lifecycle rule targets the confirmed raw prefix with INTELLIGENT_TIERING; document it.
```

### rest-api-public-endpoint
- **Title:** REST API public endpoint (US-P005) — scope + authentication model
- **Opened:** 2026-05-22
- **Status:** candidate
- **Description:** Legacy INV-2 + GAP-LD-6. The only user story never implemented; design input lives in `specs/_archive/legacy-domains/2026-06-10/applications/rest-api/{SPEC,PLAN,TASKS}.md`. Needs its own planning session (auth model: OAuth2 vs API key). Scope: outside the 2026-08-23 directive (infra/CI/Databricks). Owner: product-engineer (definition). **Proposed: defer** — not remediation; separate release after the platform is clean and fed.
- **Provenance:** intake-report item legacy INV-2/GAP-LD-6 (approved 2026-08-23 as deferred)
- **Intents:**
```yaml
- subject:
    kind: api
    ref: rest-api-public-endpoint
    surface: new
  change: Introduce the public REST API over Gold data with a decided auth model, per the archived spec-first trio as design input.
```

## LEDGER

- ideas-md-boilerplate · REJECTED · `ideas.md` held zero items ("no ideas registered"); folded as empty · 2026-08-23
- bl-01-sdd-structure-scaffold · DELIVERED · audit-remediation-r5 / v0.3.0 (bug drift-06-08 closed) · 2026-08-23
- bl-02-repo-hygiene-cleanup · DELIVERED · audit-remediation-r5 / v0.3.0 (bugs drift-02/03/04 closed) · 2026-08-23
- bl-03-release-closure-hygiene · DELIVERED · audit-remediation-r5 / v0.3.0 (bug drift-05 closed) · 2026-08-23
- bl-04-streaming-job-tests · DELIVERED · audit-remediation-r5 / v0.3.0 (bug drift-01 closed) · 2026-08-23
- bl-05-logger-best-practices-fix · DELIVERED · audit-remediation-r5 / v0.3.0 (bug bp-01 closed) · 2026-08-23
- bl-06-security-best-practices-pass · DELIVERED · audit-remediation-r5 / v0.3.0 · 2026-08-23
- bl-07-doctor-warnings-domains-migration · DELIVERED · audit-remediation-r5 / v0.3.0 (bug drift-10 closed) · 2026-08-23
- candidates-oq-decision-record-2026-05-22 · RESOLVED · grill 2026-05-22 decision record (OQ-1..7, OQ-NEW-1); OQ-1 catalog name revisited by v050-databricks-bundle-config-hardening · 2026-08-23
- low-1-api-health-50pct-prewarn · SUPERSEDED · duplicate of CAND-R4-08, itself superseded by audit-20260823 DRIFT-19 (alert bundles never deployed) · 2026-08-23
- low-2-contracts-ingestion-dead-code · RESOLVED · grill 2026-05-22 OQ-5 kept the lambda; its 2026 fate is v050-contracts-ingestion-schedule-and-lambda-path-decision · 2026-08-23
- low-3-dashboard-alert-threshold-line · SUPERSEDED · folded into ACTIVE dashboards-analytics-enrichment · 2026-08-23
- low-4-ecs-task-right-sizing · REJECTED · obsolete-by-capture-retirement (v0.4.0 removed ECS services) · 2026-08-23
- inv-1-prd-deploy-sequence-validation · REJECTED · obsolete-by-capture-retirement; HML fate + CI recovery are v050-live-infra-cleanup-hml-orphans-state-locks / v050-ci-oidc-auth-recovery · 2026-08-23
- inv-2-rest-api-scope-auth · SUPERSEDED · folded into ACTIVE rest-api-public-endpoint · 2026-08-23
- inv-3-dynamodb-block-cache-ttl · REJECTED · obsolete-by-capture-retirement (orphan detection/BLOCK_CACHE was the capture layer; DynamoDB holds 0 items) · 2026-08-23
- gap-ld-1-cicd-memory-atom · DELIVERED · v0.3.0 (cicd-pipeline.md authored at CLOSURE) · 2026-08-23
- gap-ld-2-latency-nfr-targets · REJECTED · obsolete-by-capture-retirement (Ethereum→S3 latency is dd-chain-capture's NFR) · 2026-08-23
- gap-ld-3-streaming-job-invariants · REJECTED · obsolete-by-capture-retirement (capture-layer atom is being retired) · 2026-08-23
- gap-ld-4-alerts-inventory · SUPERSEDED · audit-20260823 DRIFT-19 → ACTIVE v050-databricks-deploy-drift-redeploy-live-bundles · 2026-08-23
- gap-ld-5-scaffold-code-standards · SUPERSEDED · folded into ACTIVE v050-memory-truth-and-capture-deprecation-adr (verify-or-drop) · 2026-08-23
- gap-ld-6-rest-api-design-pointer · SUPERSEDED · duplicate of WS-3; folded into ACTIVE rest-api-public-endpoint · 2026-08-23
- cand-r2-01-kinesis-on-demand · REJECTED · obsolete-by-capture-retirement (Kinesis destroyed in v0.4.0) · 2026-08-23
- cand-r2-02-ecs-default-capacity-provider · SUPERSEDED · audit-20260823 DRIFT-13 (ECS shells deleted by v050-dead-iac-purge) · 2026-08-23
- cand-r2-03-firehose-prd-buffer · REJECTED · obsolete-by-capture-retirement (Firehose destroyed in v0.4.0) · 2026-08-23
- cand-r2-04-s3-raw-lifecycle · SUPERSEDED · folded into ACTIVE s3-raw-lifecycle-intelligent-tiering · 2026-08-23
- cand-r2-05-fargate-spot-per-service · REJECTED · obsolete-by-capture-retirement (ECS services destroyed in v0.4.0) · 2026-08-23
- cand-r2-06-dynamodb-conditional-put · REJECTED · obsolete: api_keys_manager.py is a dead module purged by v050-dead-code-and-docs-purge-capture-era · 2026-08-23
- cand-r2-07-rebuild-producer-image · REJECTED · obsolete-by-capture-retirement (producers run in dd-chain-capture) · 2026-08-23
- cand-r2-08-kms-audit-public-default-policy · SUPERSEDED · folded into ACTIVE encryption-at-rest-posture-decision · 2026-08-23
- cand-r3-01-event-time-windows · SUPERSEDED · folded into ACTIVE dlt-ethereum-data-quality-enhancements · 2026-08-23
- cand-r3-02-auto-loader-schema-evolution · SUPERSEDED · folded into ACTIVE dlt-ethereum-data-quality-enhancements · 2026-08-23
- cand-r3-03-canonical-index-window-validation · SUPERSEDED · folded into ACTIVE dlt-ethereum-data-quality-enhancements · 2026-08-23
- cand-r3-04-transactions-lambda-union · SUPERSEDED · audit-20260823 DRIFT-27 → ACTIVE v050-contracts-ingestion-schedule-and-lambda-path-decision · 2026-08-23
- cand-r3-05-drop-orphaned-gold-mvs · SUPERSEDED · folded into ACTIVE dlt-ethereum-data-quality-enhancements · 2026-08-23
- cand-r3-06-data-contract-test-suite · SUPERSEDED · audit-20260823 DRIFT-20 → ACTIVE v050-live-surface-test-pyramid · 2026-08-23
- cand-r4-01-dashboard-catalog-parameterization · SUPERSEDED · audit-20260823 DRIFT-25 → ACTIVE v050-databricks-bundle-config-hardening · 2026-08-23
- cand-r4-02-genie-instructions-block · SUPERSEDED · audit-20260823 DRIFT-19 (genie bundle never deployed) → ACTIVE v050-databricks-deploy-drift-redeploy-live-bundles · 2026-08-23
- cand-r4-03-freshness-kpi-tile · SUPERSEDED · folded into ACTIVE dashboards-analytics-enrichment · 2026-08-23
- cand-r4-04-analyst-grant-ddl · SUPERSEDED · folded into ACTIVE dashboards-analytics-enrichment · 2026-08-23
- cand-r4-05-date-range-filter · SUPERSEDED · folded into ACTIVE dashboards-analytics-enrichment · 2026-08-23
- cand-r4-06-comment-on-column · SUPERSEDED · folded into ACTIVE dashboards-analytics-enrichment · 2026-08-23
- cand-r4-07-export-gold-schedule · SUPERSEDED · audit-20260823 DRIFT-19/DRIFT-27 (export path fate) → ACTIVE v050-contracts-ingestion-schedule-and-lambda-path-decision · 2026-08-23
- cand-r4-08-api-keys-50pct-prewarn-alert · SUPERSEDED · audit-20260823 DRIFT-19 (alert bundles never deployed) → ACTIVE v050-databricks-deploy-drift-redeploy-live-bundles · 2026-08-23
- cand-r4-09-record-prd-catalog-decision · SUPERSEDED · audit-20260823 DRIFT-25 (no PRD workspace exists) → ACTIVE v050-databricks-bundle-config-hardening · 2026-08-23
- sec-hard-04-magic-constant · SUPERSEDED · audit-20260823 DRIFT-12 (source purged by v050-dead-code-and-docs-purge-capture-era) · 2026-08-23
- sec-hard-05-silent-4byte-swallow · SUPERSEDED · audit-20260823 DRIFT-12 (source purged); if utils_decode migrates, route to dd-chain-capture · 2026-08-23
- sec-hard-06-unbounded-lru-cache · SUPERSEDED · audit-20260823 DRIFT-12 (source purged) · 2026-08-23
- sec-hard-07-api-key-exhaustion-silent · SUPERSEDED · audit-20260823 DRIFT-12 (source purged) · 2026-08-23
- sec-hard-08-dockerfile-root-unpinned · SUPERSEDED · audit-20260823 DRIFT-12/DRIFT-26 (Dockerfile purged) · 2026-08-23
- sec-hard-09-pip-audit-not-run · SUPERSEDED · audit-20260823 DRIFT-06/DRIFT-07 (dependency scanning in ACTIVE v050-dependency-confusion-and-lambda-layer-rebuild) · 2026-08-23
- sec-hard-10-raw-key-tail-log · SUPERSEDED · audit-20260823 DRIFT-26 → ACTIVE v050-security-hardening-batch · 2026-08-23
- test-hard-01-fallback-log-test · SUPERSEDED · audit-20260823 DRIFT-12 (test tree purged with its subject) · 2026-08-23
- test-hard-02-dead-rotation-test · SUPERSEDED · audit-20260823 DRIFT-12 (test tree purged with its subject) · 2026-08-23
- ws-a-ci-safety-a1-a7 · DELIVERED · v0.3.0 (A1..A7 consumed) · 2026-08-23
- ws-b1-purge-infura-key-logging · DELIVERED · v0.3.0; the "key in history" claim was debunked by audit-20260823 security lane (value was an SSM parameter name) · 2026-08-23
- ws-b2-oidc-migration · DELIVERED · v0.3.0 (code-only); live cutover is ACTIVE v050-ci-oidc-auth-recovery (DRIFT-01) · 2026-08-23
- ws-b3-pr-plan-credential-isolation · DELIVERED · v0.3.0 · 2026-08-23
- ws-b4-encryption-at-rest · SUPERSEDED · Kinesis/SQS halves obsolete-by-capture-retirement; CMK residual folded into ACTIVE encryption-at-rest-posture-decision · 2026-08-23
- ws-b5-databricks-token-in-tf-state · SUPERSEDED · audit-20260823 DRIFT-26 → ACTIVE v050-security-hardening-batch · 2026-08-23
- ws-b6-low-sev-hardening-batch · SUPERSEDED · SQS/ECS items obsolete-by-capture-retirement; ECR/.gitguardian residual in audit-20260823 DRIFT-26 → ACTIVE v050-security-hardening-batch · 2026-08-23
- ws-c1-retire-prd-databricks-monolith · SUPERSEDED · audit-20260823 DRIFT-13 → ACTIVE v050-dead-iac-purge · 2026-08-23
- ws-c2-hml-must-validate-prd · SUPERSEDED · audit-20260823 DRIFT-22/DRIFT-25 (HML fate + no PRD workspace) → ACTIVE v050-live-infra-cleanup-hml-orphans-state-locks · 2026-08-23
- ws-c3-makefile-retirement · SUPERSEDED · audit-20260823 DRIFT-28 → ACTIVE v050-dead-code-and-docs-purge-capture-era · 2026-08-23
- ws-d1-single-stack-tree · SUPERSEDED · folded into ACTIVE terraform-single-stack-tree-per-env-tfvars · 2026-08-23
- ws-d2-reproducible-providers · SUPERSEDED · audit-20260823 DRIFT-15 → ACTIVE v050-ci-safety-guards-concurrency-lockfile · 2026-08-23
- ws-d3-dabs-config-dedup · SUPERSEDED · genie scaffolding → DRIFT-19; shared bundle config folded into ACTIVE terraform-single-stack-tree-per-env-tfvars · 2026-08-23
- ws-d4-module-interface-hygiene · SUPERSEDED · unused vars → DRIFT-13; rest folded into ACTIVE terraform-single-stack-tree-per-env-tfvars · 2026-08-23
- ws-d5-availability-posture-adr · REJECTED · obsolete-by-capture-retirement (FARGATE_SPOT/1-shard Kinesis gone); VPC fate is DRIFT-17 · 2026-08-23
- ws-e1-capture-deprecation-adr · SUPERSEDED · folded into ACTIVE v050-memory-truth-and-capture-deprecation-adr · 2026-08-23
- ws-e2-dead-code-infra-removal-wave · DELIVERED · v0.4.0 removed the ECS/Kinesis/SQS/Firehose surface; residual dead code/IaC is DRIFT-12/DRIFT-13 · 2026-08-23
- ws-e3-dangling-producer-decision · SUPERSEDED · audit-20260823 DRIFT-21/DRIFT-27 → ACTIVE v050-contracts-ingestion-schedule-and-lambda-path-decision · 2026-08-23
- ws-f1-architecture-md-rewrite · SUPERSEDED · audit-20260823 DRIFT-04 → ACTIVE v050-memory-truth-and-capture-deprecation-adr · 2026-08-23
- ws-f2-data-catalog-adr-005-truth · SUPERSEDED · audit-20260823 DRIFT-04/DRIFT-27 · 2026-08-23
- ws-f3-close-fixed-bugs-doctor-errors · DELIVERED · v0.3.0 (8 bugs closed, doctor 0 errors) · 2026-08-23
- ws-f4-retire-specs-domains-legacy-tree · DELIVERED · v0.3.0 (T-R6-S4 archived legacy-domains) · 2026-08-23
- ws-f5-wire-streaming-tests-into-ci · REJECTED · obsolete: the streaming tests cover retired code; live-surface CI wiring is DRIFT-20 → ACTIVE v050-live-surface-test-pyramid · 2026-08-23
- ws-f6-quality-assurance-atom · SUPERSEDED · audit-20260823 DRIFT-04 (quality-assurance stale) → ACTIVE v050-live-surface-test-pyramid / memory residual · 2026-08-23
- ws-f7-capture-supersession-in-memory · SUPERSEDED · folded into ACTIVE v050-memory-truth-and-capture-deprecation-adr · 2026-08-23
- ws-g1-working-tree-pollution · SUPERSEDED · audit-20260823 DRIFT-29 → ACTIVE v050-quality-gates-ruff-mypy-worktree · 2026-08-23
- ws-g2-branch-model-decision · SUPERSEDED · audit-20260823 DRIFT-10 → ACTIVE v050-repo-governance-branch-protection-default-branch · 2026-08-23
- op-r6-1-infura-key-rotation · REJECTED · debunked by audit-20260823 security lane (logged value was an SSM parameter name, not a key); SSM key-inventory ownership stays with the operator · 2026-08-23
- op-r6-2-oidc-provider · RESOLVED · GitHub OIDC provider exists in the account (audit-20260823 LA-03) · 2026-08-23
- ws-1-3-apply-03-iam-set-role-vars · SUPERSEDED · audit-20260823 DRIFT-01/DRIFT-08 → ACTIVE v050-ci-oidc-auth-recovery · 2026-08-23
- ws-1-4-hml-required-reviewers · SUPERSEDED · audit-20260823 DRIFT-10 → ACTIVE v050-repo-governance-branch-protection-default-branch · 2026-08-23
- ws-1-5-four-role-assumption-evidence · SUPERSEDED · audit-20260823 DRIFT-01 → ACTIVE v050-ci-oidc-auth-recovery · 2026-08-23
- ws-1-6-live-oidc-validation · SUPERSEDED · audit-20260823 DRIFT-01 → ACTIVE v050-ci-oidc-auth-recovery · 2026-08-23
- ws-1-7-live-hml-graduation · SUPERSEDED · audit-20260823 DRIFT-02/DRIFT-22 (HML gate + HML fate) · 2026-08-23
- op-r6-4-static-key-deletion · SUPERSEDED · audit-20260823 DRIFT-09 → ACTIVE v050-public-repo-secret-store-and-pii-hygiene · 2026-08-23
- ws-2-code-reviewer-cleanups · SUPERSEDED · dead `local root=` + stale comment folded into ACTIVE v050-ci-safety-guards-concurrency-lockfile; PowerUserAccess → DRIFT-08 · 2026-08-23
- ws-3-memory-gaps-gap-ld-2-6 · SUPERSEDED · duplicate of candidates.md GAP-LD-2..6 (dispositioned above) · 2026-08-23
