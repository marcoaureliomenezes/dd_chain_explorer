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
> **Purge-on-pick v0.6.0 (2026-08-23).** The operator demand `three-repo-segregation-migration`
> (grill-me 2026-08-23, 2 rounds, 9 ADRs, operator-confirmed — handoff
> `2026-08-23T203850Z-project-manager-grillme-3repo-segregation`; approved intake by direct
> operator ratification) was picked by release v0.6.0 in the commit that created
> `specs/releases/v0.6.0/SPEC.md` — its `**Consumes:**` line is the provenance. LEDGER line
> at v0.6.0 CLOSURE's disposition sweep.
>
> **Purge-on-pick (2026-08-23).** The 18 `v050-*` entries picked by release v0.5.0 left ACTIVE in
> the commit that created `specs/releases/v0.5.0/SPEC.md` (its `**Consumes:**` line is the provenance,
> together with the intake report above). LEDGER lines are added at CLOSURE's disposition sweep.
> The 7 deferred entries remain ACTIVE.

> **Restart intake (2026-09-13).** Grill-me 2026-09-12/13 (2 rounds, rulings R1-R17, handoff
> `.dadaia/handoff/dd-chain-explorer/2026-09-13T011657Z-project-manager-restart-audit-grill`) is
> approved intake by direct operator ratification: the platform pivots to financial-asset data
> (Ibovespa company metrics first). Ruling R1 PARKS the Ethereum lane: the five Ethereum-era
> entries below (`dlt-ethereum-data-quality-enhancements`, `dashboards-analytics-enrichment`,
> `s3-raw-lifecycle-intelligent-tiering`, `rest-api-public-endpoint`, `encryption-at-rest-posture-decision`)
> stay ACTIVE but are not pickable while the lane is parked; they gain a LEDGER line when the lane is
> retired or revived. Capture-side scope lives in `dd-chain-capture/specs/backlog/candidates.md`
> (`financial-capture-ibovespa-metrics`).
>
> **Amendment pick v0.7.0 (2026-09-23).** Operator rulings R18-R22 (recorded in
> `batch-medallion-and-ethereum-retirement` and `cicd-zero-manual-steps`) amend the Approved
> v0.7.0 SPEC in place: `batch-medallion-and-ethereum-retirement`, `cicd-zero-manual-steps` and
> `e2e-dev-validation-financial-lakehouse` turn `picked (v0.7.0)` in the SPEC-amendment commit
> (its `**Consumes:**` line is the provenance); LEDGER lines at v0.7.0 CLOSURE. R21 supersedes R1:
> the five parked Ethereum-era entries exit at that CLOSURE as `REJECTED · obsolete-by-R21`
> (SPEC §7) — four since the second amendment below.
>
> **Amendment pick v0.7.0 (2) (2026-09-23).** Operator rulings R27-R36 (grill, operator-confirmed;
> recorded in `databricks-serverless-us-east-1-migration`) amend the v0.7.0 SPEC in place again:
> the Free Edition workspace is abandoned (R18 struck), DEV and PROD become serverless workspaces
> in the operator's Databricks account, everything moves to us-east-1. The new entry and
> `capture-ecr-state-and-kms-ownership-transfer` (closed by R34) turn `picked (v0.7.0)` in that
> SPEC-amendment commit; LEDGER lines at CLOSURE. R30 un-parks
> `encryption-at-rest-posture-decision`, rewritten as the future cost×security study and pickable.
> `prod-environment-official-account` is narrowed to what v0.7.0 does not build (the first PRD
> workload).

## ACTIVE

### market-data-medallion-restart
- **Title:** Medallion lakehouse for Ibovespa company metrics over the new financial raw landing (dev first)
- **Opened:** 2026-09-13
- **Status:** picked (v0.7.0, pre-staged; shape amended 2026-09-23 — batch job, not DLT, R19; Ethereum destroyed, R21)
- **Description:** Operator demand (grill 2026-09-12/13). After v0.6.0 closes (R5): (a) infra — new dev raw bucket `dm-chain-explorer-dev-raw-data` (no expiry, Intelligent-Tiering, R14), ECR repositories + `gha_capture_publish` OIDC role in the bootstrap (R12), Fargate scheduled-task stacks for the three capture images (R2), UC external location + `databricks_grants` for the SP on the new landing (R9); (b) explorer — new DLT bundle(s) reading `raw/<source>/<dataset>/ingest_date=*/` untouched bytes (R13) into bronze (b3 cotahist, ibov portfolio, consolidated files; cvm cadastro/fca, dfp/itr, fre/ipe; bcb sgs), silver normalization (Latin-1, fixed-width, restatement dedupe by VERSAO), gold company-metrics computed from statements x prices (P/L, P/VP, EV/EBITDA, ROE, ROIC, margins, DL/EBITDA, CAGR, DY) per `dd-chain-capture/docs/research/ibovespa-metrics-source-study.md`; (c) Ethereum DAB resources stay undeployed (R1). Dev only; PRD-compatible design, no PRD resources (R4). Consumer: the consumer agent in dadaia-agents, record only (R10).
- **Provenance:** grill-me 2026-09-12/13 rulings R1-R17 (approved 2026-09-13, operator ratification)
- **Intents:**
```yaml
- subject:
    kind: code
    ref: apps/dabs/
  change: One market-data batch bundle (serverless job, bronze → silver → gold, file-arrival trigger) lands Ibovespa company metrics from the new raw landing; every Ethereum bundle is destroyed (R19-R21).
- subject:
    kind: doc
    ref: memory/product/capture-layer.md
  change: Capture integration describes the Fargate batch images and the raw/<source>/<dataset>/ingest_date contract; the Ethereum streaming lane is retired (R21).
```

### e2e-dev-validation-financial-lakehouse
- **Title:** End-to-end DEV validation — capture image run → S3 raw → bronze → silver → gold rows queryable (the POC gate)
- **Opened:** 2026-09-20
- **Status:** picked (v0.7.0 SPEC amendment 2026-09-23 — closure gate AC-22, R22; blocks `prod-environment-official-account` and `financial-sources-expansion-data-model`)
- **Description:** Operator demand 2026-09-20 (direct, recorded here as intake): the platform must prove ONE unbroken flow in DEV with the minimum set of sources before anything else — a published capture image executed as a Fargate task (or the operator-run `make batch-smoke-real`) lands untouched bytes + `_manifest.json` in `s3://dm-chain-explorer-dev-raw-data/raw/<source>/<dataset>/ingest_date=*/`; the `dlt_market_data` bundle deployed to `dev` ingests them into `b_market` (Auto Loader), materializes `s_market`, and produces `g_market` rows (`company_daily_prices`, `ibov_weights_daily`, `company_fundamentals_snapshot`, `macro_daily`) queryable from SQL. Evidence = row counts per layer for one ingest_date plus the manifest sha match, recorded in the v0.7.0 CLOSURE. Nothing here is new code: it is the live execution of what v0.7.0 already built (infra stacks + bundle) and the operator lane T-O7.1..T-O7.4 + T-X7.6. Live state on 2026-09-20: AWS has no dev raw bucket, no batch ECR repos, no capture cluster; Databricks `dev` has zero pipelines/jobs and only Ethereum schemas; all four PRs open, nothing merged. **Proposed: fold as the mandatory acceptance of v0.7.0** (no separate release) — the POC is "done" only when this entry's evidence exists.
- **Shape (2026-09-23, R19/R20):** batch, not Auto Loader/DLT. The landed partition fires the `job_market_data` serverless job (file-arrival trigger on `_manifest.json`); three PySpark tasks write `b_market`/`s_market`/`g_market` Delta tables (12/8/3) by MERGE/overwrite; gold tables are the SPEC X5 set (`company_daily_price`, `ibov_constituents_daily`, `company_fundamentals_snapshot`; BCB series stay silver context). The partition comes from a workflow-run Fargate task, not the hand smoke (`cicd-zero-manual-steps`). A second fire over the same partition changes no count.
- **Provenance:** operator demand 2026-09-20 (session-bound dd-chain-explorer; restart grill R4 "DEV FIRST" and R16 "first milestone = images writing to S3" are the prior rulings it sharpens)
- **Intents:**
```yaml
- subject:
    kind: doc
    ref: releases/v0.7.0/CLOSURE.md
  change: The CLOSURE carries the end-to-end evidence table — one ingest_date, raw objects + manifest sha, bronze/silver/gold row counts from the dev workspace, trigger job state.
- subject:
    kind: code
    ref: apps/dabs/job_market_data/
  change: The batch bundle is deployed to dev from CI and its job has run at least once from a file-arrival fire over real landed bytes; no Ethereum resource exists.
```

### batch-medallion-and-ethereum-retirement
- **Title:** Medallion becomes batch Databricks Jobs (no DLT) triggered by file arrival; the Ethereum lane is destroyed everywhere
- **Opened:** 2026-09-23
- **Status:** picked (v0.7.0 SPEC amendment 2026-09-23; the e2e gate is proven on the batch shape)
- **Description:** Operator rulings 2026-09-23 (grill, session-bound dd-chain-explorer): ~~**R18** the Free Edition workspace is DEV only (ADR-10 reaffirmed)~~ — struck 2026-09-23 by R27 (`databricks-serverless-us-east-1-migration`). **R19** processing is batch — no DLT for now: `dlt_market_data` (streaming tables + MVs, T-X7.1..X7.5) is replaced by one bundle with one serverless Databricks Job, three chained PySpark tasks bronze → silver → gold writing Delta by MERGE/overwrite; the pure parsers already tested are reused. **R20** the job fires on a Databricks file-arrival trigger over the raw landing (`_manifest.json`), not a cron and not a GitHub Actions call. **R21** the Ethereum lane dies everywhere, superseding R1 "parked": Databricks — 7 empty schemas (`b_ethereum`, `b_app_logs`, `s_apps`, `s_logs`, `g_network`, `g_apps`, `g_api_keys`) and 7 SP bundle state dirs; code — 7 bundles in `apps/dabs/` (`dlt_ethereum`, `dlt_app_logs`, `job_export_gold`, 4 dashboards); AWS — `dm-dev-ingestion` bucket + external location, DynamoDB, Lambdas (contracts-ingestion, gold_to_dynamodb), ECR stream/connect repos, PRD schedule `dm-dd-chain-explorer-prd-contracts-ingestion-hourly`; all removed through IaC/CI, never by hand (see `cicd-zero-manual-steps`). **R22** this rework lands inside v0.7.0, not a new release.
- **Provenance:** operator demand 2026-09-23
- **Intents:**
```yaml
- subject:
    kind: code
    ref: apps/dabs/
  change: One batch market-data bundle (job + 3 tasks + file-arrival trigger) is the only bundle; every Ethereum bundle is gone.
- subject:
    kind: doc
    ref: releases/v0.7.0/SPEC.md
  change: The SPEC is amended to the batch shape and the Ethereum destruction scope; TASKS replace the DLT tasks.
```

### cicd-zero-manual-steps
- **Title:** The whole deploy chain runs from GitHub Actions — every manual step taken to reach the DEV e2e is recorded here and replaced by a workflow
- **Opened:** 2026-09-23
- **Status:** picked (v0.7.0 SPEC amendment 2026-09-23 — closure gate AC-24 beside AC-22, R22; blocks `prod-environment-official-account`)
- **Description:** Operator demand 2026-09-23 (direct): "every manual step must be recorded, and at the end absolutely everything is automated — deploy workflows in GitHub Actions; the CI/CD must end fully automated". A green e2e reached by hand-run commands is not done. Acceptance: from a clean `develop` merge, the chain infra → artifacts/images → UC → bundle deploy → capture run → pipeline update runs with no human command except approving a GitHub environment gate; the only irreducible manual act is ONE documented trust seed (AWS bootstrap role + Databricks SP identity + its secret), run once per account and scripted. **Manual-step ledger (append each new one as it happens):**
  - M1 `prd/00_bootstrap` applied locally with admin creds (09-18, 09-21 delta 4 changes, 09-21 re-apply 8 changes after infra #6) — seed, keep but script it.
  - M2 hml stack destroyed locally (ADR-6 exception) — one-off, retired env.
  - M3 `publish_oidc_vars.sh --apply` run locally to set `AWS_DEPLOY_ROLE_*`, `AWS_ARTIFACTS_PUBLISH_ROLE`, `AWS_CAPTURE_PUBLISH_ROLE` repo variables — should be a bootstrap-lane output step.
  - M4 GitHub environments created/deleted by hand (capture `dev`+`production`; hml envs in infra/explorer); capture `develop` branch created via API — should be declared (Terraform `github` provider or a repo-settings workflow).
  - M5 GitHub secrets set by hand: explorer env `dev` `DATABRICKS_*`; infra repo `DATABRICKS_HOST/CLIENT_ID/CLIENT_SECRET/DEV_SP_APPLICATION_ID/UC_EXTERNAL_ID` (09-04 values stored EMPTY because `gh secret set` had no TTY).
  - M6 Databricks SP client secret minted by hand.
  - M7 Databricks grants by hand: SP `MANAGE` on catalog `dev`, `CREATE_EXTERNAL_LOCATION` on credential `dm-dev-s3-credential` (09-21); pending 09-23: SP `CREATE_EXTERNAL_LOCATION` on metastore `metastore_aws_us_east_2` (DEV run 35804683061 failed on it).
  - M8 Hand-made Databricks objects outside IaC: catalog `dev`, credential `dm-dev-s3-credential`, external location `dm-dev-ingestion`.
  - M9 Ethereum jobs/pipelines/dashboards deleted via CLI (09-13, R1).
  - M10 Hand PRs `develop → main` in infra and explorer only so `workflow_dispatch` workflows exist on the default branch.
  - M11 Hand dispatches: `deploy_cloud_infra` PRD; DEV always with `force_apply=true` (dispatch from develop diffs against origin/develop → every stack "unchanged"); `deploy-dabs` with a bundle filter.
  - M12 Hand `gh run rerun --failed` of explorer `publish-artifacts` and capture `publish-images` after infra applied — cross-repo ordering carried by a human.
  - M13 Hand `databricks pipelines start-update` of `[dev] dm-market-data`.
  - M14 Pending: first capture run by hand (`aws ecs run-task` / `make batch-smoke-real`); schedules deployed `DISABLED`.
  - M15 Drift Detection runs on infra `main` while deploys come from `develop` → permanent false drift until someone ships `develop → main` by hand.
  Structural causes to fix (not symptoms): no cross-repo orchestration (`workflow_run`/`repository_dispatch`), dev lane change-detection wrong for dispatch, Databricks identity/grants outside Terraform, GitHub settings outside code, deploy branch ≠ drift branch.
- **Provenance:** operator demand 2026-09-23 (session-bound dd-chain-explorer, mid DEV forced dispatch)
- **Intents:**
```yaml
- subject:
    kind: code
    ref: .github/workflows/
  change: One orchestrated lane per environment chains infra, artifacts, images, UC, bundle deploy, capture run and pipeline update with no hand command beyond an environment approval.
- subject:
    kind: doc
    ref: releases/v0.7.0/CLOSURE.md
  change: The CLOSURE lists every M-step of this entry with the workflow that replaced it, or the single scripted trust seed it folded into.
```

### databricks-serverless-us-east-1-migration
- **Title:** DEV + PROD on serverless Databricks workspaces in the operator's account, everything in us-east-1 — Free Edition abandoned
- **Opened:** 2026-09-23
- **Status:** picked (v0.7.0 SPEC amendment (2) 2026-09-23 — I12-I15, AC-25..30)
- **Description:** Operator demand 2026-09-23 (grill, operator-confirmed), after the Free Edition workspace blocked v0.7.0 (no compute: warehouse refusals, `RESOURCE_EXHAUSTED`, 403 "organization cancelled"; metastore owned by "System user", so `CREATE_EXTERNAL_LOCATION` cannot be granted; UC objects hand-made, M7/M8) and a study showed a serverless workspace in a Databricks-on-AWS account has zero fixed cost, no VPC/NAT, and external tables on our S3. Rulings: **R27** retire ADR-10/R18 — Free Edition abandoned, DEV+PROD = serverless workspaces in the operator's existing (empty, Premium, card-billed) Databricks account. **R28** PROD permanent + rebuildable (drill), no destroy strategy. **R29** region us-east-1 for everything incl. state, list-price saving ~25.7% (Databricks −25%, AWS −38%) to be measured at CLOSURE. **R30** SSE-S3 only, no CMK — cost×security trade-off to be studied later (`encryption-at-rest-posture-decision`). **R31** one us-east-1 metastore, catalogs dev/prd ISOLATED, storage_root on per-env lakehouse bucket, external tables only. **R32** new bucket names `dm-chain-explorer-<env>-<purpose>` + new tf-state bucket, sa-east-1 buckets (verified empty 2026-09-23) deleted via CI. **R33** S3-native TF locking (`use_lockfile`), DynamoDB lock table removed. **R34** orphan `capture/ecr` state destroyed entirely (11 resources incl. KMS + Roles Anywhere) — closes `capture-ecr-state-and-kms-ownership-transfer`. **R35** `develop` default branch in infra + explorer. **R36** file events enabled on the storage credential. Shape: account Databricks stack (metastore, 2 serverless workspaces, per-env deploy SPs, budget alert); per-workspace UC stack rebuildable from git; GitHub stack (App-authenticated) writing environments, secrets, variables and the default branch; the trust seed shrinks to S1 bootstrap / S2 GitHub App / S3 account-SP secret; sa-east-1 torn down through CI before the us-east-1 bring-up. Folds into v0.7.0 (no new release) per the amendment-pick convention.
- **Provenance:** operator demand 2026-09-23 (session-bound dd-chain-explorer; grill rulings R27-R36; serverless-workspace cost study)
- **Intents:**
```yaml
- subject:
    kind: doc
    ref: releases/v0.7.0/SPEC.md
  change: The SPEC records R27-R36 and carries the region, SSE-S3, platform, rebuild-drill and cost ACs (AC-25..30); TASKS drop the Free Edition tasks and gain the account, region and GitHub stacks.
- subject:
    kind: doc
    ref: memory/product/aws-resources.md
  change: Every project resource and the Terraform state live in us-east-1 with SSE-S3 and S3-native locking; nothing remains in sa-east-1.
- subject:
    kind: doc
    ref: releases/v0.7.0/CLOSURE.md
  change: The CLOSURE carries the rebuild-drill evidence and the before/after cost table (list price + 7 days of system.billing.usage, % saving).
```

### prod-environment-official-account
- **Title:** PROD front — the first PRD workload (gated bundle deploy + PRD capture schedules) on the platform v0.7.0 builds
- **Opened:** 2026-09-20
- **Status:** candidate (blocked-by `e2e-dev-validation-financial-lakehouse`; narrowed 2026-09-23 by R27-R28)
- **Narrowed (2026-09-23, R27-R31):** v0.7.0 now builds the PRD platform — the PROD serverless workspace in the operator's Databricks account, its deploy SP, catalog `prd` (ISOLATED), the PRD raw/lakehouse buckets, the PRD UC stack and the `production` environment (`databricks-serverless-us-east-1-migration`); the `prod` bundle target is validated, never deployed. **What remains here:** deploy `job_market_data` to `prod` through the `production` gate; a PRD capture runtime (`dev/03_capture` shape) with `schedules_enabled = true`; PRD data retention; a PRD cost ceiling beside the budget alert; who approves the `production` gate. Grill still required for those.
- **Description (original, 2026-09-20):** Operator demand 2026-09-20, front 1 after the POC gate. Stand up the production side declared-but-not-created since ADR-10 (R4: design PRD-compatible now, create nothing until gold is worth it): official-account SP + UC catalog/schemas + external location on the PRD raw bucket, `prod` target of the market-data bundle (`job_market_data` since R19) deployed through the `production` environment gate, PRD capture schedules (`dev/03_capture` shape reused, `schedules_enabled = true`), cost ceiling stated in the SPEC. Grill required (account, catalog naming, cost, retention, who approves the production gate).
- **Provenance:** operator demand 2026-09-20
- **Intents:**
```yaml
- subject:
    kind: doc
    ref: memory/product/environments.md
  change: prod runs a workload — the market-data job deployed through the production gate and PRD capture schedules enabled — documented as live, not declared.
```

### financial-sources-expansion-data-model
- **Title:** Sources front — more financial sources + a real data model feeding rich gold tables for dashboards and the investment agent
- **Opened:** 2026-09-20
- **Status:** candidate (blocked-by `e2e-dev-validation-financial-lakehouse`)
- **Description:** Operator demand 2026-09-20, front 2 after the POC gate. Beyond the three POC images (B3 cotahist/ibov/consolidated, CVM cadastro/statements/documents, BCB SGS): find further official/free sources (grill R6 order: official APIs first, scraping last) for B3 company financials and metrics; design the dimensional/semantic model (companies, instruments, calendar, statements, prices, macro) so silver combines sources and gold exposes valuation/quality/growth metrics (P/L, P/VP, EV/EBITDA, ROE, ROIC, margins, DL/EBITDA, CAGR, DY — study `dd-chain-capture/docs/research/ibovespa-metrics-source-study.md`); first Databricks dashboards over `g_market`; the consumer contract for the investment agent in dadaia-agents (R10). Capture-side images are a `dd-chain-capture` candidate; this entry owns the model, the medallion layers (batch since R19) and the dashboards.
- **Provenance:** operator demand 2026-09-20
- **Intents:**
```yaml
- subject:
    kind: code
    ref: apps/dabs/job_market_data/
  change: Silver joins multiple sources through a documented data model; gold exposes the metric set above with tests per metric; at least one dashboard bundle reads g_market.
- subject:
    kind: doc
    ref: memory/product/data-model.md
  change: The financial data model (entities, keys, grain, source lineage per column) is product memory.
```

### capture-ecr-state-and-kms-ownership-transfer
- **Title:** Move the dd-chain-capture `capture/ecr` Terraform state + KMS key out of this repo's state bucket (or document the hosting)
- **Opened:** 2026-08-23
- **Status:** picked (v0.7.0 SPEC amendment (2) 2026-09-23 — R34 destroys the orphan state whole through CI, AC-26; exits `DELIVERED` at CLOSURE)
- **Resolution (2026-09-23, R34):** the move is not needed — `capture/ecr` (11 resources incl. KMS `alias/dd-chain-capture-ssm`, Roles Anywhere, the empty `stream`/`connect` ECR repos) has no source and no consumer, so v0.7.0 destroys it entirely through CI before the region switch and the state key leaves the bucket.
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
    ref: apps/dabs/dlt_ethereum/src/streaming/ethereum_pipeline.py#gold_block_production_health
  change: Gold MVs declare table/column COMMENTs in the DLT definitions; analyst GRANTs are applied via Unity Catalog (the standalone DDL job was retired in v0.5.0 — objects are DLT-owned).
```

### encryption-at-rest-posture-decision
- **Title:** Encryption-at-rest study — cost × security of SSE-S3 vs SSE-KMS/CMK for the financial lakehouse buckets, Terraform state and Databricks storage
- **Opened:** 2026-05-22 (rewritten 2026-09-23, R30)
- **Status:** candidate (pickable — un-parked by R30 from the R1/R21 Ethereum-era set; no longer exits as `obsolete-by-R21`)
- **Description:** Operator ruling R30 (2026-09-23): v0.7.0 ships SSE-S3 (AES256) everywhere with no CMK; the cost×security trade-off is studied later, here. Study scope: the us-east-1 buckets (`dm-chain-explorer-<env>-raw-data`/`-lakehouse`, tf-state), the UC storage credential path and Databricks workspace storage; for each, SSE-S3 vs SSE-KMS (AWS-managed key) vs CMK (with S3 Bucket Keys) — KMS request and key cost at the measured object volume, what a CMK adds (key-policy separation of duties, revocation, CloudTrail per-decrypt audit) against the threat model of public market data vs the credentials-bearing state; Databricks customer-managed keys only if the account tier allows. Output: a recommendation with a monthly cost delta and an ADR proposal for the operator. Replaces the Ethereum-era scope (DynamoDB/Kinesis CMK, KMS bill audit — the DynamoDB table and the capture KMS key are destroyed in v0.7.0, R21/R34). Scope: infra-terraform + security lens. Owner: code-reviewer (security lens) → software-engineer.
- **Also in scope (2026-09-23 finding):** the operator AWS profile `admin` is an IAM user with long-term admin access keys and NO MFA; once the trust seed runs and CI deploys via OIDC, study disabling/rotating those keys (or MFA-gated role only) as part of the same cost×security decision.
- **Provenance:** intake-report item legacy CAND-R2-08 + WS-B/B4 residual (approved 2026-08-23 as deferred); rewritten by operator ruling R30 (grill 2026-09-23)
- **Intents:**
```yaml
- subject:
    kind: doc
    ref: memory/product/aws-resources.md
  change: The encryption-at-rest posture per bucket (SSE-S3 or KMS/CMK) is stated with the cost × security rationale, backed by an operator-accepted ADR.
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
