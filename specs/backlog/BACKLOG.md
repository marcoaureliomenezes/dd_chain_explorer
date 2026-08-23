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

## ACTIVE

### v050-ci-oidc-auth-recovery
- **Title:** CI cannot authenticate to AWS — apply least-privilege OIDC roles + set `AWS_DEPLOY_ROLE_*` vars
- **Opened:** 2026-08-23
- **Status:** candidate
- **Description:** DRIFT-01 (CRITICAL) + DRIFT-08 (HIGH). All 55 `configure-aws-credentials` steps read `vars.AWS_DEPLOY_ROLE_{DEV,HML,PRD,READONLY}` which do not exist; the 4 roles in `services/prd/03_iam/oidc.tf` were never applied. Before any apply, rewrite the roles to least-privilege (today: `PowerUserAccess` + inline `iam:*Role*` on `*` = admin escalation; read-only role trusts any-branch `pull_request` + `ReadOnlyAccess`). Then apply `prd/03_iam`, set the 4 repo variables, record role-assumption evidence per env. Supersedes legacy WS-1 #3/#5/#6 and WS-2 PowerUserAccess. Scope: ci-github-actions + infra-terraform. Owner: software-engineer (roles/IaC), security-reviewer (policy verdict), operator (apply + vars). **Proposed: pick v0.5.0** (prerequisite for every other CI item).
- **Provenance:** intake-report item DRIFT-01/DRIFT-08 (approved 2026-08-23, operator directive)
- **Intents:**
```yaml
- subject:
    kind: doc
    ref: memory/tech-stack.md#cicd
  change: Rewrite the 4 OIDC roles to least-privilege scoped policies (no PowerUserAccess, no iam:*Role* on '*'), restrict the read-only role trust to this repo's PR claims, apply them, and document the live role ARNs + the 4 AWS_DEPLOY_ROLE_* repo variables.
- subject:
    kind: doc
    ref: memory/product/cicd-pipeline.md#dependências
  change: State the real auth dependency (4 repo variables + applied roles) and the evidence of a green OIDC assume-role run per environment.
```

### v050-deploy-workflow-capture-lane-purge
- **Title:** Purge the retired capture lane from `deploy_all_dm_applications.yml` and its CI scripts
- **Opened:** 2026-08-23
- **Status:** candidate
- **Description:** DRIFT-02 (CRITICAL). The only app-deploy workflow still builds the stream image, provisions HML Kinesis/SQS (`scripts/ci/hml_provision.sh` hard-fails on destroyed queues), launches 5 ECS producers, updates 5 destroyed PRD services, runs `terraform destroy -target=module.kinesis` on a deleted module, and gates on an unconditional `exit 0` (`hml_integration_test_optimized.sh`); PRD DABs + Lambda deploys are chained behind it. Remove the capture lane, delete the dead CI scripts, keep DABs + Lambda deploy as first-class jobs, and make the gate real. Scope: ci-github-actions. Owner: software-engineer; qa-engineer validates the new gate. **Proposed: pick v0.5.0.**
- **Provenance:** intake-report item DRIFT-02 (approved 2026-08-23, operator directive)
- **Intents:**
```yaml
- subject:
    kind: catalog
    ref: cicd-pipeline
  change: The app-deploy workflow deploys only the live surface (DABs bundles + Lambdas); no ECS/Kinesis/SQS/Firehose/stream-image step survives, and the HML gate is a real check, not `exit 0`.
- subject:
    kind: doc
    ref: memory/product/cicd-pipeline.md#fluxo-de-uso
  change: Rewrite the deploy flow to the post-capture-retirement job graph (plan → apply → DABs → Lambda), naming the scripts that remain under scripts/ci/.
```

### v050-ci-safety-guards-concurrency-lockfile
- **Title:** CI safety: wire `scripts/ci/tests`, fix `stack_map.json`, add `concurrency:`, commit `.terraform.lock.hcl`
- **Opened:** 2026-08-23
- **Status:** candidate
- **Description:** DRIFT-14 + DRIFT-15 (HIGH) + legacy WS-2 cleanups + WS-D/D2 + CI F-19/LA-13 (LOW). `scripts/ci/tests/` (45 guard tests) runs in no workflow; `stack_map.json` declares `modules: []` for DEV stacks that consume 4 modules (a test enshrines it) and 4 phantom prd edges; stack lists hard-coded in 4 places. The 25-job deploy workflow has no `concurrency:` (deploy vs destroy can race one state); `-auto-approve` under reviewer-less `hml-apps`; no lockfile anywhere (floating `aws >= 5.0`), TF version drift 1.7→1.15; `destroy_all` omits `hml/05b_databricks_workspace`; `auto-bump-version` pushes from detached HEAD; `destroy_cloud_infra.yml:103` direct interpolation; dead `local root=` + stale comment in `deploy_env.sh`/`plan_env.sh`. Scope: ci-github-actions + infra-terraform. Owner: software-engineer. **Proposed: pick v0.5.0.**
- **Provenance:** intake-report item DRIFT-14/DRIFT-15 (approved 2026-08-23, operator directive); legacy WS-2 (v0.3.0 CLOSURE deferral, pre-approved)
- **Intents:**
```yaml
- subject:
    kind: code
    ref: scripts/ci/changed_stacks.py#load_map
  change: stack_map.json becomes the single, correct source (DEV module edges declared, phantom prd edges removed, hard-coded stack lists in workflows derived from it) and scripts/ci/tests run in CI on every PR.
- subject:
    kind: doc
    ref: memory/product/cicd-pipeline.md#estado-real-e-lacunas
  change: Document the stack-map truth and the CI job that enforces it.
- subject:
    kind: doc
    ref: memory/tech-stack.md#infrastructure-as-code
  change: One pinned terraform + provider version repo-wide with committed .terraform.lock.hcl per stack; concurrency groups per environment shared by deploy and destroy; destroy_all covers every stack.
```

### v050-repo-governance-branch-protection-default-branch
- **Title:** Branch protection, `main` as default branch, `plan_on_pr` on the shipping PR, stale-branch sweep
- **Opened:** 2026-08-23
- **Status:** candidate
- **Description:** DRIFT-10 (HIGH) + legacy WS-G/G2. No protection on `master`/`develop`; `plan_on_pr.yml` only triggers on PRs to `develop` so the shipping PR gets no fmt/validate/plan; `hml` environment has no reviewers, `hml-apps` does not exist; default branch is `master` (192 ahead / 4 behind, different workflow set) so `drift_detection` cron never fires; 10 stale remote branches. Align with the `dadaia-gitflow` contract (`main` default, PR `develop→main` only, protected). Scope: ci-github-actions. Owner: software-engineer (workflow triggers), operator (GitHub settings via gh). **Proposed: pick v0.5.0.**
- **Provenance:** intake-report item DRIFT-10 (approved 2026-08-23, operator directive)
- **Intents:**
```yaml
- subject:
    kind: doc
    ref: memory/product/cicd-pipeline.md#trigger-típico
  change: plan_on_pr fires on PRs to both develop and the default branch; drift_detection schedule fires from the default branch; document the branch model (main default + protected, develop only pushable).
- subject:
    kind: doc
    ref: memory/product/cicd-pipeline.md#propósito
  change: Record branch protection rules, environment reviewers (hml, hml-apps) and the default-branch decision as product truth.
```

### v050-version-axis-unification
- **Title:** One version axis: `VERSION`/tags vs SDD release ids vs `__version__` vs DABs `VERSION` files
- **Opened:** 2026-08-23
- **Status:** candidate
- **Description:** DRIFT-11 (HIGH). `VERSION`=0.2.9 / tags `v0.2.9-*` (CI auto-bump) vs SDD releases v0.3.0 shipped / v0.4.0; no `v0.3.0*`/`v0.4.0*` tag; a PRD deploy today would mint `v0.2.10-infra`; lib `__version__` 0.1.0; 15 DABs `VERSION` files at 1.0.0 so `deploy_all.sh` would SKIP all 15. Decide the single axis (SDD release id), make CI tag from it, drop the auto-bump mint. Scope: ci-github-actions. Owner: software-engineer. **Proposed: pick v0.5.0.**
- **Provenance:** intake-report item DRIFT-11 (approved 2026-08-23, operator directive)
- **Intents:**
```yaml
- subject:
    kind: doc
    ref: memory/tech-stack.md#version-axes
  change: Declare the single version axis (SDD release id = VERSION = git tag = lib __version__) and the rule that DABs bundle VERSION files track it; remove the auto-bump patch mint.
```

### v050-public-repo-secret-store-and-pii-hygiene
- **Title:** Public repo hygiene: delete dangling static AWS keys + capture-era secrets, rotate IAM key, service principal for DABs `run_as`
- **Opened:** 2026-08-23
- **Status:** candidate
- **Description:** DRIFT-09 (HIGH) + legacy WS-1 #8 (OP-R6-4). Repo is PUBLIC: static `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` (2026-03-20) + `DYNAMODB_TABLE`/`ECS_TASK_*_ROLE_ARN` sit unreferenced in the GitHub secret store; the CI IAM user still holds 2 active access keys; the operator's personal e-mail is hard-coded as `run_as.user_name` in 12 DABs prod targets; workspace host in 12 bundles. Delete secrets + keys (after OIDC evidence, see v050-ci-oidc-auth-recovery), replace `run_as` with a service principal, move host/account identifiers to variables, confirm public posture. Scope: ci-github-actions + databricks-artifacts + live-ops. Owner: security-reviewer (verdict), software-engineer (bundles), operator (secret store + IAM). **Proposed: pick v0.5.0.**
- **Provenance:** intake-report item DRIFT-09 (approved 2026-08-23, operator directive); legacy WS-1 #8 (v0.3.0 CLOSURE deferral, pre-approved)
- **Intents:**
```yaml
- subject:
    kind: doc
    ref: memory/architecture.md#adr-006-ssm-as-the-shared-secret-plane
  change: DABs run_as uses a service principal (no personal e-mail in any bundle); workspace host comes from a variable/profile, not a literal in 12 bundles.
- subject:
    kind: doc
    ref: memory/product/cicd-pipeline.md#estado-runtime-tocado
  change: The GitHub secret store holds zero static AWS credentials and zero capture-era secrets; the CI IAM user has no active access keys; record the deletion evidence.
```

### v050-dependency-confusion-and-lambda-layer-rebuild
- **Title:** Close the `dm-chain-utils` dependency-confusion hole and rebuild the Lambda layer from source in CI
- **Opened:** 2026-08-23
- **Status:** candidate
- **Description:** DRIFT-06 + DRIFT-07 (HIGH). `dm-chain-utils==0.2.9` is pinned in 3 production manifests + Dockerfile and installed from the public index while the name is unclaimed on PyPI (404) — fails closed by luck; `>=` floors make CVE scans a false negative. The committed 37 MB `dm_chain_utils_layer.zip` (built 2026-03 from another codebase, 31 CVEs / 4 packages, contains 0.1.0 while CI asserts 0.2.9 by text grep) is what Terraform ships (`source_code_hash`); 5 binary artifacts tracked. Install only from the local `utils/` build (`--no-index`/path), pin with hashes, build the layer in CI, stop tracking binaries. Scope: lambda. Owner: software-engineer; security-reviewer verifies. **Proposed: pick v0.5.0.**
- **Provenance:** intake-report item DRIFT-06/DRIFT-07 (approved 2026-08-23, operator directive)
- **Intents:**
```yaml
- subject:
    kind: doc
    ref: memory/tech-stack.md#shared-library-dm-chain-utils
  change: dm-chain-utils is installed only from the in-repo utils/ build (never the public index); manifests are hash-pinned; the library version equals the single version axis.
- subject:
    kind: doc
    ref: memory/tech-stack.md#lambda-functions-appslambda
  change: The Lambda layer zip is built reproducibly in CI from utils/ and is not tracked in git; Terraform source_code_hash comes from the CI artifact.
```

### v050-dead-code-and-docs-purge-capture-era
- **Title:** Delete the 16 dead capture-era modules (~4,540 LOC, 44 %), their tests, dead scripts, `img/` slop, and capture-era docs
- **Opened:** 2026-08-23
- **Status:** candidate
- **Description:** DRIFT-12 (HIGH) + DRIFT-28 (MEDIUM) + legacy WS-C/C3 + `streaming-jobs-security-hardening` residue. 6/9 `dm_chain_utils` modules have zero live callers (`dm_kinesis`, `dm_sqs`, `dm_firehose`, `dm_web3_client`, `dm_cloudwatch_logger`, `api_keys_manager`) yet are re-exported and shipped in the layer (+ `web3`/`hexbytes` chain); all of `apps/docker/onchain-stream-txs/**` (2,867 LOC, unbuildable image); `scripts/prod_ecs_logs.py`; 6 unreferenced scripts; `img/` slop. README/AGENTS.md/apps READMEs cite 16 nonexistent Makefile targets and describe Firehose/ECS/Kinesis; DLT notebook headers, DDL comments, `apps/dabs/README.md`, DEPLOYMENT_GUIDE, `dev_dlt_integration_test.sh` prerequisite likewise. Every test deletion is a qa-engineer verdict executed by software-engineer (`dadaia-test-stewardship`). Scope: dead-code. Owner: software-engineer + qa-engineer. **Proposed: pick v0.5.0.**
- **Provenance:** intake-report item DRIFT-12/DRIFT-28 (approved 2026-08-23, operator directive)
- **Intents:**
```yaml
- subject:
    kind: code
    ref: utils/src/dm_chain_utils/dm_kinesis.py#KinesisHandler
  change: Delete the module and its tests; drop the re-export.
- subject:
    kind: code
    ref: utils/src/dm_chain_utils/dm_sqs.py#SQSHandler
  change: Delete the module and its tests; drop the re-export.
- subject:
    kind: code
    ref: utils/src/dm_chain_utils/dm_firehose.py#FirehoseHandler
  change: Delete the module and its tests; drop the re-export.
- subject:
    kind: code
    ref: utils/src/dm_chain_utils/dm_web3_client.py#Web3Handler
  change: Delete the module and its tests; drop web3/hexbytes from the dependency chain.
- subject:
    kind: code
    ref: utils/src/dm_chain_utils/dm_cloudwatch_logger.py#CloudWatchLoggingHandler
  change: Delete the module and its tests; drop the re-export.
- subject:
    kind: code
    ref: utils/src/dm_chain_utils/api_keys_manager.py#APIKeysManager
  change: Delete the module and its tests (closes legacy CAND-R2-06 as obsolete).
- subject:
    kind: code
    ref: apps/docker/onchain-stream-txs/src/4_mined_txs_crawler.py#RawTransactionsProcessor
  change: Delete apps/docker/onchain-stream-txs/** (all 5 jobs, utils_decode, tests, Dockerfile) — the producers run in dd-chain-capture; closes SEC-HARD-04..09 and TEST-HARD-01/02 as source-purged.
- subject:
    kind: doc
    ref: memory/tech-stack.md#dependências-aprovadas
  change: Remove the streaming-application section (or reduce it to a pointer to dd-chain-capture).
- subject:
    kind: doc
    ref: memory/product/index.md#mapa-de-capacidades
  change: Module inventory lists only the 3 live dm_chain_utils modules and the live scripts; README/AGENTS.md/apps READMEs cite only existing targets and the post-retirement data path.
```

### v050-dead-iac-purge
- **Title:** Remove dead Terraform: ECS shells, firehose branch, Kinesis/Firehose/SQS IAM grants, `prd/05_databricks` monolith, unused vars
- **Opened:** 2026-08-23
- **Status:** candidate
- **Description:** DRIFT-13 (HIGH) + legacy WS-C/C1 + CAND-R2-02. ECS shells in `prd/07_ecs`, `hml/07_ecs`, `modules/ecs` (cluster + capacity providers + 2 ECR repos, 0 services; 4 dead locals); firehose branch of `modules/cloudwatch_logs` universally `count=0` (+ `outputs.tf:17` `[0]` index risk); Kinesis/Firehose/SQS grants in `prd/03_iam/iam.tf:57-92`, `hml/03_iam/main.tf:91-123` (creates a firehose role), `modules/iam` with name-pattern wildcards that resurrect by name; `prd/05_databricks` 524-line monolith (own backend key never created, absent from stack map); `kinesis_sqs` remote-state alias; 6 unused variables; `modules/s3` `prevent_destroy` var ignored. Scope: infra-terraform. Owner: software-engineer; security-reviewer verifies IAM delta. **Proposed: pick v0.5.0.**
- **Provenance:** intake-report item DRIFT-13 (approved 2026-08-23, operator directive)
- **Intents:**
```yaml
- subject:
    kind: catalog
    ref: aws-resources
  change: The Terraform tree declares only live resources — no ECS cluster/capacity providers/ECR shells, no firehose branch, no Kinesis/Firehose/SQS IAM grants, no prd/05_databricks monolith, no kinesis_sqs alias, no unused variables.
- subject:
    kind: doc
    ref: memory/product/aws-resources.md#ecs-ecr-and-network-residue
  change: IAM section lists only the grants the live surface needs (DLT/UC S3 access, Lambda roles, OIDC deploy roles); no capture-era name-pattern wildcards.
- subject:
    kind: doc
    ref: memory/architecture.md#ordem-de-deploy-terraform-prd
  change: Deploy order lists only the surviving stacks and equals stack_map.json.
```

### v050-live-infra-cleanup-hml-orphans-state-locks
- **Title:** Live AWS cleanup: force-unlock 2 stale state locks, decide HML fate, sweep leaked SGs/log groups/task-defs/orphan roles + lambda
- **Opened:** 2026-08-23
- **Status:** candidate
- **Description:** DRIFT-16 (stale locks since 2026-04-22 on `prd/databricks-account` + `hml/peripherals`), DRIFT-17 (24 leaked `dm-hml-sg-<run>` SGs in `ChainExplorer-vpc`, which CI secret `HML_VPC_ID` proves is the unmanaged HML substrate), DRIFT-22 (HML half-alive: state claims 2 buckets that 404, 19 live IAM resources unused since 04-09, 42 `hml-*` log groups, 60 task-def revisions, DABs-referenced hml buckets missing, `hml` UC catalog empty), DRIFT-24 (legacy lambda `dd-chain-explorer-dev-gold-to-dynamodb` + role + LG, `dm-databricks-dev-s3-role` undocumented Free-Edition UC credential, `dm-hml-firehose-role`, lambda LGs without retention, phantom `raw/.keep`). Operator decision #5: destroy `hml/iam` + `state rm` phantoms, or re-apply HML; import or retire `ChainExplorer-vpc`. Scope: live-ops + infra-terraform. Owner: software-engineer (terraform/import/state), operator (AWS mutations). **Proposed: pick v0.5.0.**
- **Provenance:** intake-report item DRIFT-16/17/22/24 (approved 2026-08-23, operator directive)
- **Intents:**
```yaml
- subject:
    kind: doc
    ref: memory/architecture.md#topologia-de-ambientes
  change: Environment topology states the decided HML fate (destroyed or re-applied from Terraform), the managed status of the HML VPC, and that no state lock is stale and no phantom resource is in state.
- subject:
    kind: doc
    ref: memory/product/aws-resources.md#cloudwatch-log-groups
  change: Log-group inventory equals live (hml-* groups swept or re-owned; retention on every Lambda log group).
- subject:
    kind: doc
    ref: memory/product/aws-resources.md#iam-roles
  change: IAM inventory equals live (orphan dm-hml-firehose-role / legacy dev lambda role removed; dm-databricks-dev-s3-role either documented + imported or removed).
```

### v050-contracts-ingestion-schedule-and-lambda-path-decision
- **Title:** Disable the no-op hourly PRD `contracts-ingestion` schedule; decide the `export_gold → gold_to_dynamodb → DynamoDB` path
- **Opened:** 2026-08-23
- **Status:** candidate
- **Description:** DRIFT-21 (MEDIUM) + DRIFT-27 + legacy WS-E/E3 + CAND-R3-04. PRD `contracts-ingestion` runs hourly (168 inv/7 d, `contracts_processed:0`, DynamoDB 0 items) burning Etherscan quota since capture retirement. `job_export_gold → S3 exports → gold_to_dynamodb λ → DynamoDB PK=CONSUMPTION` fed the retired Job 4's `APIKeysManager`; no in-repo reader remains. ADR-005 Lambda-architecture UNION (`gold_transactions_lambda`) documented but never built. Operator decision #2: pause the schedule now; keep-and-rewire (dd-chain-capture reads it) or descope the whole chain + ADR-005 and rewrite memory. Scope: lambda. Owner: software-engineer; product-engineer (ADR/memory). **Proposed: pick v0.5.0** (schedule disable is immediate; path decision at grill).
- **Provenance:** intake-report item DRIFT-21/DRIFT-27 (approved 2026-08-23, operator directive)
- **Intents:**
```yaml
- subject:
    kind: code
    ref: apps/lambda/contracts_ingestion/handler.py#handler
  change: Hourly PRD schedule disabled until a real contract feed exists; lambda either rewired to the decided feed or descoped with its EventBridge rule.
- subject:
    kind: code
    ref: apps/lambda/gold_to_dynamodb/handler.py#handler
  change: Keep (with a named consumer, e.g. dd-chain-capture) or remove the lambda + S3 notifications + DynamoDB table per the operator decision; never leave it running for no reader.
- subject:
    kind: code
    ref: apps/dabs/dlt_ethereum/src/streaming/ethereum_pipeline.py#gold_transactions_lambda
  change: Implement the UNION with a Silver intermediary, or drop the MV together with ADR-005 — one or the other, decided at grill.
- subject:
    kind: doc
    ref: memory/architecture.md#adr-005-lambda-architecture-for-transactions
  change: ADR-005 is either implemented or formally superseded; memory states which.
- subject:
    kind: doc
    ref: memory/product/aws-resources.md#gold-exports-job_export_gold-the-export-lambdas-trigger-prefix
  change: Section describes the decided state of the export path (live with consumer, or removed).
```

### v050-databricks-deploy-drift-redeploy-live-bundles
- **Title:** Databricks: redeploy `dm-app-logs` (Fluent-Bit reader) + hml `dm-ethereum`, fix broken trigger/full-refresh/reconcile jobs, alert/genie no-ops, dropped `schedule:`
- **Opened:** 2026-08-23
- **Status:** candidate
- **Description:** DRIFT-18 + DRIFT-19 (HIGH) + DBX-13 (LOW) + CAND-R4-02/R4-07/R4-08 + GAP-LD-4. Deployed `dm-app-logs` in both targets is the old CloudWatch `binaryFile` UDF reader — the Fluent-Bit NDJSON fix (2026-05-23) never deployed; hml `dm-ethereum` is pre-R1 with bucket ≠ bundle. `dm-trigger-all-dlts` (dev+hml) and hml `dm-dlt-full-refresh` deployed with empty `pipeline_id`; `dm-reconcile-orphan-blocks` notebook deleted (`67f8faf`) but job scheduled UNPAUSED daily; full-refresh wheel absent; `alert_*`/`genie_ethereum` bundles use resource types unknown to the CLI → 0 resources, never deployed (memory says DEV validated); DLT `schedule:` is an unknown field, silently dropped; `.bundle/dd-chain-explorer` stale remote state + orphan queries/credential/catalogs. Scope: databricks-artifacts. Owner: software-engineer; qa-engineer validates deploy. **Proposed: pick v0.5.0.**
- **Provenance:** intake-report item DRIFT-18/DRIFT-19 (approved 2026-08-23, operator directive)
- **Intents:**
```yaml
- subject:
    kind: catalog
    ref: medallion-pipelines
  change: Deployed DLT code equals the repo in every target; companion jobs (trigger, full-refresh, reconcile, delta-maintenance, export) reference real pipeline ids/notebooks/wheels or are deleted; DLT scheduling uses a supported mechanism.
- subject:
    kind: code
    ref: apps/dabs/dlt_app_logs/src/streaming/app_logs_pipeline.py#_auto_loader_fluentbit
  change: The Fluent-Bit NDJSON reader is the deployed dm-app-logs in dev (and hml if HML survives), verified by a deploy evidence run.
- subject:
    kind: doc
    ref: memory/product/medallion-pipelines.md#pipeline-dm-app-logs
  change: Describe the Fluent-Bit reader as the deployed pipeline, with the bronze/silver logger-name filters updated for the dd-chain-capture producers.
- subject:
    kind: doc
    ref: memory/product/medallion-pipelines.md#scheduling-and-companion-jobs
  change: Trigger job documented with its real pipeline ids and schedule mechanism.
- subject:
    kind: doc
    ref: memory/product/serving-layer.md#known-gaps
  change: Genie + alert bundles either deployed with a supported resource type (and Genie `instructions:` block) or removed from the tree and from memory; no "validated SUCCEEDED" claim for an undeployed asset.
```

### v050-databricks-bundle-config-hardening
- **Title:** DABs config: prod target host guard, dashboards parameterized by catalog, embed setting, DDL/maintenance ownership fixes
- **Opened:** 2026-08-23
- **Status:** candidate
- **Description:** DRIFT-25 (MEDIUM) + legacy WS-D/D3 (genie scaffolding) + CAND-R4-01 + CAND-R4-09 + OQ-1 revisit. prod target `host: ""` falls back to the DEFAULT profile — `validate -t prod` passes ×15 and a `deploy -t prod` would create `prd`-catalog assets on Free Edition (there is no PRD workspace); 4 dashboards hard-code `dev.` catalog in SQL; published `embed_credentials=true` vs bundle `false`; `job_ddl_setup` pre-creates DLT-owned tables and `job_delta_maintenance` OPTIMIZE/VACUUMs ST/MVs (unsupported). Scope: databricks-artifacts. Owner: software-engineer. **Proposed: pick v0.5.0.**
- **Provenance:** intake-report item DRIFT-25 (approved 2026-08-23, operator directive)
- **Intents:**
```yaml
- subject:
    kind: catalog
    ref: serving-layer
  change: Dashboards take the catalog from a bundle variable (no hard-coded dev.), embed setting matches the bundle, and the prod target either names a real host or is removed.
- subject:
    kind: doc
    ref: memory/product/serving-layer.md#fluxo-de-uso
  change: Document the catalog parameterization and the per-target dashboard deploy truth.
- subject:
    kind: doc
    ref: memory/architecture.md#adr-002-one-databricks-workspace-catalogs-as-environments
  change: Catalog convention states the live reality (Free Edition, dev/hml catalogs; prd only if a PRD workspace exists) — revisits the OQ-1 decision.
- subject:
    kind: code
    ref: apps/dabs/job_ddl_setup/src/dd_chain_explorer/ddl/setup_ddl.py#DDChainExplorerDDL
  change: DDL setup no longer pre-creates DLT-owned tables; delta maintenance skips streaming tables / MVs.
```

### v050-security-hardening-batch
- **Title:** Security batch: Databricks token out of TF state, pinned actionlint, key-tail log leak, bulk-decrypt helper, ECR/SG/SQL hardening
- **Opened:** 2026-08-23
- **Status:** candidate
- **Description:** DRIFT-26 (MEDIUM) + legacy WS-B/B5, WS-B/B6, SEC-HARD-10. Databricks bootstrap token persisted cleartext in S3 TF state (`05*/outputs.tf:9`); unpinned `curl | bash` actionlint installer in a PR-triggered job; Etherscan key-tail log leak (`etherscan_multi.py:115` — goes away with the docker purge, verify no copy in `dm_etherscan`); latent `ParameterStoreClient.list_parameters()` bulk decryption; ECR `MUTABLE` + `force_delete`; SG all-protocol ingress from VPC CIDR; f-string SQL in `job_ddl_setup`. Scope: infra-terraform + ci-github-actions + databricks-artifacts. Owner: software-engineer; security-reviewer verdict. **Proposed: pick v0.5.0.**
- **Provenance:** intake-report item DRIFT-26 (approved 2026-08-23, operator directive)
- **Intents:**
```yaml
- subject:
    kind: doc
    ref: memory/tech-stack.md#databricks
  change: No Databricks token is persisted in Terraform state or outputs (sensitive + short-lived auth); record the mechanism.
- subject:
    kind: doc
    ref: memory/tech-stack.md#external-apis
  change: No API key fragment is ever logged; ParameterStoreClient exposes no bulk-decrypt helper; document the key-handling rule.
```

### v050-live-surface-test-pyramid
- **Title:** Tests for the live surface (lambdas, DABs jobs, DLT expectations) and CI runs every suite; retire the inverted pyramid
- **Opened:** 2026-08-23
- **Status:** candidate
- **Description:** DRIFT-20 (HIGH) + QA F8 + legacy WS-F/F5 + CAND-R3-06. 113/158 tests cover retired code; 0 tests on `apps/lambda` (392 LOC), `apps/dabs` (~3,800 LOC), the 3 live utils modules, DLT expectations; CI runs only `utils/tests/unit` (dead-module tests gate the lambda build); no Terraform policy tooling; tests lack intent/size declarations. After the dead-code purge, write the minimal live pyramid (unit for lambdas + 3 utils modules, contract tests for DABs/DLT expectations, `scripts/ci/tests` in CI), declare intent + size on every test. Scope: ci-github-actions. Owner: qa-engineer (strategy + verdicts), software-engineer (tests). **Proposed: pick v0.5.0.**
- **Provenance:** intake-report item DRIFT-20 (approved 2026-08-23, operator directive)
- **Intents:**
```yaml
- subject:
    kind: doc
    ref: memory/quality-assurance.md#inventário-atual
  change: Inventory lists the live suites (lambda, utils live modules, DABs/DLT contracts, scripts/ci/tests) with counts and the CI job that runs each; no retired-code suite remains.
- subject:
    kind: doc
    ref: memory/quality-assurance.md#contrato-de-testes-a-pirâmide-pretendida
  change: Gaps list is rewritten to the post-purge reality (remaining untested live paths, if any).
- subject:
    kind: doc
    ref: memory/quality-assurance.md#review-gates
  change: CI gate runs every suite on every PR; every test declares intent + size (dadaia-test-stewardship).
```

### v050-quality-gates-ruff-mypy-worktree
- **Title:** Add ruff/mypy config + CI gate, format the tree, fix working-tree pollution and duplicate `test/`+`tests/` trees
- **Opened:** 2026-08-23
- **Status:** candidate
- **Description:** DRIFT-29 (MEDIUM) + legacy WS-G/G1. No ruff/mypy config; 46/60 files unformatted; 36 default-rule ruff errors (7 `F821 spark`, 19 F401); mypy 13 errors default / 48 strict on `utils/src`; working-tree pollution (`.hypothesis/`, 16 `apps/dabs/*/.databricks/` with nested `.terraform/`); duplicate `test/`+`tests/` trees. Scope: ci-github-actions. Owner: software-engineer. **Proposed: pick v0.5.0.**
- **Provenance:** intake-report item DRIFT-29 (approved 2026-08-23, operator directive)
- **Intents:**
```yaml
- subject:
    kind: doc
    ref: memory/quality-assurance.md#padrões-de-qualidade
  change: ruff format/check + mypy configured in pyproject and enforced in CI; zero errors at HEAD.
- subject:
    kind: doc
    ref: memory/tech-stack.md#development-tools
  change: Development tools list ruff/mypy config and the clean-tree recipe; .gitignore covers .databricks/, .terraform/, .hypothesis/; one tests/ tree per app.
```

### v050-memory-truth-and-capture-deprecation-adr
- **Title:** Memory truth residual after v0.4.0 CLOSURE: capture-layer deprecation ADR, stale atoms, `index.md` vs `catalog.json`
- **Opened:** 2026-08-23
- **Status:** candidate
- **Description:** DRIFT-04 (HIGH) + legacy WS-E/E1, WS-F/F1/F2/F6/F7, GAP-LD-5, CAND-R4-09. At audit time 6 atoms were STALE/DEAD (~40 claims): `architecture.md` (4-layer system whose first layer was deleted; 3/6 ADRs describe the superseded event bus, no superseding ADR), `tech-stack.md`, `product/aws-resources.md`, `product/capture-layer.md`, `index.md` ≠ `catalog.json`, `data-catalog`/`medallion-pipelines` (30 vs 29 objects), `serving-layer`, `quality-assurance`, `cicd-pipeline`. v0.4.0 CLOSURE (in progress 2026-08-23) rewrites part of this — at pick time re-diff memory vs live and keep only the residual. The formal deprecation ADR (capture layer superseded by dd-chain-capture; S3 = integration boundary; sunset criteria) was never written. Verify whether the `beteugeuse` scaffold rule (GAP-LD-5) is still current or drop it. Scope: specs-governance. Owner: product-engineer. **Proposed: pick v0.5.0** (residual only).
- **Provenance:** intake-report item DRIFT-04 (approved 2026-08-23, operator directive); legacy WS-E/E1 (2026-06-11 audit ARCH-H5)
- **Intents:**
```yaml
- subject:
    kind: catalog
    ref: capture-layer
  change: The feature atom is retired or rewritten as the dd-chain-capture boundary contract (bucket/prefix/format/field names) — no description of ECS/Kinesis/Firehose/SQS as live.
- subject:
    kind: doc
    ref: memory/architecture.md#limites-conhecidos
  change: Add the capture-layer deprecation ADR superseding ADR-001/002/006 (which stay as history, marked superseded); ADR-003 scoped to what survives.
- subject:
    kind: doc
    ref: memory/architecture.md#camadas
  change: Layer model describes the live 3-layer system (S3 boundary fed by dd-chain-capture → DLT medallion → serving/export) with no deleted first layer.
- subject:
    kind: doc
    ref: memory/product/index.md#catálogo-de-features
  change: index.md equals catalog.json (same feature set and keys); every atom's claims re-verified against live after v0.4.0 CLOSURE.
```

### v050-audit-dispositions-constitution-bug-ledger
- **Title:** Disposition both open audits, author a real `constitution.md`, clean the bug ledger (misfiled tooling bug, `drift-04` timestamp)
- **Opened:** 2026-08-23
- **Status:** candidate
- **Description:** DRIFT-05 (HIGH) + DRIFT-31 (MEDIUM) + DRIFT-03 verification. The 2026-06-11 audit (70 findings) has zero per-finding dispositions two months on; today's audit (DRIFT-01..31) must be dispositioned 1:1 by v0.5.0's TASKS/CLOSURE, then both archive naming v0.5.0. `specs/constitution.md` is a 33-byte stub (231-line version survives only in `_archive/legacy-memory`). The single open bug `sdd-artifact-linter-mutates-task-markers` is a dadaia-workspace tooling bug misfiled here — append a terminal event here that routes it upstream (re-register in the dadaia-workspace ledger); `drift-04` resolved event timestamp precedes its reported evidence (document). Verify v0.4.0 is closed (CLOSURE, memory, archive, merge, push) before v0.5.0 definition starts. Scope: specs-governance. Owner: product-engineer (constitution, CLOSURE dispositions), project-manager (archives, bug routing). **Proposed: pick v0.5.0.**
- **Provenance:** intake-report item DRIFT-05/DRIFT-31 (approved 2026-08-23, operator directive)
- **Intents:**
```yaml
- subject:
    kind: doc
    ref: constitution.md#product-law
    surface: new
  change: Author specs/constitution.md from the live product (scope, stack, environments, data boundary with dd-chain-capture, quality bar) replacing the 33-byte stub.
- subject:
    kind: doc
    ref: memory/architecture.md#visão-geral
  change: Overview cites the constitution and names the two dispositioned audits and the release that dispositioned them.
```

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
