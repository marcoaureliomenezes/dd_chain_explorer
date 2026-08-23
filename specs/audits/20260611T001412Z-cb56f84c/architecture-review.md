# Architecture Review — dd-chain-explorer

> **Auditor:** software-architect (REVIEW mode)
> **Timestamp:** 2026-06-11T00:14:12Z
> **Scope:** AWS topology, Terraform architecture, environment parity, Databricks/DABs, dead/legacy code
> **Method:** architect-core-workflow (problem understood → prior art surveyed) + full-tree inspection via Read/Glob/Grep. No production file touched.
> **Prior art consulted:** `specs/audits/20260609T013037Z/audit.md` (6.2/10), `specs/backlog/rebuild-abandoned-r2-r3-r4-capabilities.md`, active release `audit-remediation-r5`, sibling repo `dd-chain-capture` (capture-layer replacement, S3 = integration boundary). Findings already tracked there are referenced, not duplicated.

---

## 0. Core Workflow Trail

- **Core problem:** determine whether the implemented AWS + Terraform + Databricks architecture matches the documented architecture (`specs/memory/architecture.md`, `specs/domains/*`), and whether it is maintainable by a human without AI help.
- **Constraints:** single-operator project; cost-sensitive (sa-east-1, no NAT GW, spot, standby-at-zero); capture layer being replaced by `dd-chain-capture` (VPS + Kafka + Redis), S3 remains the only integration boundary.
- **Success criteria:** every drift between declared and real architecture named with file:line; env parity matrix produced; dead/legacy inventory produced; each finding has WHY + TRADE-OFF.
- **Assumptions made explicit:** (a) `deploy_env.sh` + GitHub workflows are the production deploy path, the Makefile is not; (b) `desired_count = 0` on all ECS services reflects deliberate standby, not abandonment; (c) live AWS/Databricks state was not inspectable (no credentials) — all evidence is code-level.

**Verdict summary: 2 CRITICAL, 6 HIGH, 10 MEDIUM, 8 LOW.**
**Architecture-fidelity gate: REJECTED** — `specs/memory/architecture.md` and the domain SPECs misrepresent the implemented S3 topology, IAM scopes, naming, HML lifecycle, and Databricks environment model (see H3, M1, M2, M4). The corrections required are listed per finding.

---

## 1. CRITICAL findings

### [CRITICAL] C1 — Two live Terraform control planes for PRD Databricks (stale layer never deleted)
**Location:** `services/prd/05_databricks/` (entire stack) vs `services/prd/05a_databricks_account/` + `services/prd/05b_databricks_workspace/`; `Makefile:369-377` (`tf_apply_databricks` → `05_databricks`), `Makefile:401-406` (`tf_init_prd` includes `05_databricks`, excludes 05a/05b), `scripts/tf_validate_all.sh:35`; vs `scripts/ci/deploy_env.sh:138-184` (deploys 05a + 05b only).
**Issue:** The legacy monolith `05_databricks` (state key `prd/databricks/terraform.tfstate`, `main.tf:15-22`) declares the **same account-level resources** as the new split stacks — `databricks_mws_credentials "dm"` named `dm-chain-explorer-credentials` (`05_databricks/databricks.tf:5-10`), `databricks_metastore "dm"` named `dm-chain-explorer-metastore` (`databricks.tf:205-214`), workspace, storage config, external locations — under a **different state key** than `05a` (`prd/databricks-account`) and `05b` (`prd/databricks-workspace`). CI deploys the new pair; the Makefile and `tf_validate_all.sh` still operate the old monolith. Provider/version constraints also diverge (`>= 4.60.0` AWS in the 05x stacks vs `>= 5.0` everywhere else).
**Why it matters:** this is the exact "code stacked on a stale layer" pattern that produces untraceable incidents. Anyone running `make tf_apply_databricks` (the documented Makefile path) against an environment deployed by CI will either error on duplicate account-level names or — worse — adopt/destroy resources tracked by the other state. `prevent_destroy` on the metastore lives in the **stale** stack (`05_databricks/databricks.tf:213`), not in 05a, so the protection people think exists is attached to the dead copy.
**Trade-off if fixed:** deleting `05_databricks` costs a careful state check (confirm `prd/databricks/terraform.tfstate` is empty or migrated) and Makefile/script edits; it buys a single source of truth for the most dangerous stack in the repo.
**Recommendation:** delete `services/prd/05_databricks/` entirely; repoint `Makefile` Databricks targets and `tf_validate_all.sh:35` to 05a/05b; verify the `prd/databricks` state object in S3 is empty before removal; move `prevent_destroy` guards onto the live resources in 05a.

### [CRITICAL] C2 — The HML validation gate does not test what PRD runs (split-brain bucket + split-brain workspace)
**Location:** `apps/dabs/dlt_ethereum/databricks.yml:53` (`ingestion_s3_bucket: "dm-chain-explorer-hml-raw"`); `services/hml/04_peripherals/main.tf:154-175` (Firehose for blocks/txs delivers to `module.s3_lakehouse` = `dm-chain-explorer-hml-lakehouse`, prefix `raw/`); all other bundles use `hml-lakehouse` (`dlt_app_logs/databricks.yml:47`, `job_ddl_setup:40`, `job_export_gold:39`, `job_full_refresh:45`, `job_reconcile_orphans:40`); CI gold validation reads `s3://dm-chain-explorer-hml-lakehouse/raw/` (`.github/workflows/deploy_all_dm_applications.yml:582-586`); `apps/dabs/README.md:171` documents `hml-lakehouse` as canonical. Additionally `services/hml/05_databricks/` provisions a full **MWS workspace** per CI run (dynamic URL), while every bundle's `hml` target hardcodes the shared dev workspace `https://dbc-409f1007-5779.cloud.databricks.com` (`dlt_ethereum/databricks.yml:49` and 14 siblings).
**Issue:** two independent contradictions in the only pre-PRD gate: (1) the **main** DLT pipeline's HML target Auto-Loads from a bucket that Firehose never writes block/tx data to (only `app_logs` goes to `hml-raw` via `cloudwatch_logs`, `main.tf:134-147`); (2) HML DABs deploys land on the *shared dev workspace* with an `[hml]` name prefix, not on the MWS workspace that `deploy_env.sh:103-108` spends CI time and money creating. `specs/memory/architecture.md:160` compounds this by claiming HML Databricks is "Free Edition".
**Why it matters:** the HML stage either validates against empty inputs (false confidence) or validates a different workspace/auth/catalog topology than PRD (untested PRD path). A green HML run proves almost nothing about the PRD `dm-ethereum` pipeline — this is how broken releases reach production "fully tested".
**Trade-off if fixed:** one-line bucket fix is free; deciding the HML workspace model (use the terraform-provisioned MWS workspace via injected `DATABRICKS_HOST`, or delete `hml/05_databricks` and accept prefix-isolation on the shared workspace) trades CI cost/fidelity — but either decision beats the current split-brain.
**Recommendation:** fix `dlt_ethereum/databricks.yml:53` → `dm-chain-explorer-hml-lakehouse` immediately. Then make ONE decision on the HML Databricks model, record it as an ADR in memory, and delete the losing half (`hml/05_databricks`+`05b` OR the hardcoded hosts).

---

## 2. HIGH findings

### [HIGH] H1 — PRD and HML are built from different Terraform codepaths
**Location:** HML composes shared modules — `services/hml/02_vpc/main.tf:46` (`modules/vpc`), `hml/03_iam/main.tf:55` (`modules/iam`), `hml/07_ecs/main.tf:55` (`modules/ecs`). PRD hand-rolls the same infrastructure inline — `prd/02_vpc/network.tf`, `prd/03_iam/iam.tf` (250+ lines), `prd/07_ecs/ecs.tf` (380 lines of repeated task-definition blocks). `modules/ecs`, `modules/iam`, `modules/vpc` are **never used by PRD**.
**Issue:** the environment that matters most (PRD) does not exercise the shared modules; the environment that exists to validate PRD (HML) is built from different code. Peripherals are a third pattern: three near-copies (`dev/01_peripherals/main.tf`, `hml/04_peripherals/main.tf`, `prd/04_peripherals/peripherals.tf`) instead of one root + per-env tfvars.
**Why it matters:** env parity becomes unverifiable by construction — every PRD change must be manually mirrored into module code and vice versa, and the drift already exists (HML ECS cluster is a bare module call; PRD ECS has Cloud Map, circuit breakers, 5 inline task defs HML never sees). "Tested in HML" is structurally weaker than it looks.
**Trade-off if fixed:** converging PRD onto the modules (or per-env tfvars over one root) is a state-surgery project (moved resources / `terraform state mv`), but it converts env parity from a manual promise into a property of the code.
**Recommendation:** pick one composition model. Minimum viable: make PRD `07_ecs` and `03_iam` consume the same modules HML uses, with a documented diff-list of intentional PRD-only features.

### [HIGH] H2 — The Makefile is a stale parallel control plane with broken targets
**Location:** `Makefile:314-318` (`publish_apps` pushes retired Docker Hub images `spark-batch-jobs`/`onchain-batch-txs` with undefined `$(current_branch)`); `Makefile:327-330` (`deploy_dev_all` → `services/compose/airflow_orchestration_layer.yml`, path does not exist; Airflow exists nowhere in the repo); `Makefile:408-409` (`tf_apply_remote_state` → `$(TF_DIR)/0_remote_state`, does not exist — real stack is `01_tf_state`); `Makefile:390-395` (`prod_destroy_infra` calls `tf_destroy_free_resources`, a target that does not exist → make error mid-destroy); `Makefile:332-343` (comments reference module numbering `3_kinesis_sqs`, `9_dynamodb`, `6_ecs`, `10_lambda` from a previous tree layout); `Makefile:306,363` reference `scripts/setup_databricks_profiles.sh` and `.github/workflows/deploy_infrastructure.yml`, neither exists; `Makefile:37,197` claim "16 bundles" — there are 15.
**Issue:** the 23 KB Makefile encodes at least three generations of the project (Airflow/Spark era, pre-split numbering era, current). Live targets (`tf_apply_databricks` → C1) sit beside dead ones with no marking.
**Why it matters:** the Makefile is the first thing a human operator reads. Half its targets either fail, deploy the stale Databricks stack, or push images for a dead architecture. This is exactly the "human cannot safely operate the repo without AI help" failure mode.
**Trade-off if fixed:** an afternoon of deletion; risk is removing a target someone still uses — mitigated by the fact several are provably broken (undefined vars, nonexistent paths) so nobody can be using them.
**Recommendation:** delete `publish_apps`, `deploy_dev_all`, `tf_apply_remote_state`, fix or delete `prod_destroy_infra`, repoint Databricks targets per C1, fix stale comments and counts. Keep only targets that the CI scripts don't already own, and say so in the header.

### [HIGH] H3 — `specs/memory/architecture.md` misrepresents the implemented architecture (fidelity gate REJECT)
**Location / contradictions:**
| Memory claim | Reality |
|---|---|
| `architecture.md:47-48,161` — Firehose delivers to raw bucket `dm-chain-explorer-raw-data` | PRD Firehose (blocks, decoded txs, Kinesis-sourced, app_logs) all deliver to the **lakehouse** bucket `raw/` prefix — `prd/04_peripherals/peripherals.tf:103,151`; DABs prod `ingestion_s3_bucket: dm-chain-explorer-lakehouse` (`dlt_ethereum/databricks.yml:68`). `raw-data` bucket exists but is bypassed by the streaming flow |
| `architecture.md:100-103` — task role SQS/Kinesis ARNs `mainnet-*`, SSM `parameter/dm-chain-explorer/*` | `prd/03_iam/iam.tf:67,77,92` scopes `mainnet-*-prd` / `firehose-mainnet-*-prd`; SSM grants are `/web3-api-keys/*` + `/etherscan-api-keys/*` (`iam.tf:146-147`); plus an undocumented Secrets Manager grant (`iam.tf:114-121`) |
| `tech-stack.md:96-103` — PRD resources carry **no** env suffix | modules append `-${environment}` to every queue/stream/firehose (`modules/sqs/main.tf:50`, `modules/kinesis/main.tf:41,137`): real names are `mainnet-mined-blocks-events-prd`, etc. |
| `architecture.md:160` — HML Databricks "Free Edition" | `hml/05_databricks/databricks.tf:109-122` provisions a full MWS workspace |
| `architecture.md:85-91` — replicas 1/1/1/6/3 live in PRD | all 5 ECS services `desired_count = 0` with `ignore_changes` (`prd/07_ecs/ecs.tf:244,260` etc.) — fleet is in standby, scaled by `scripts/prod_resume.sh` outside Terraform |

**Why it matters:** memory is the contract every agent and human plans against. Each of these five misstatements would send an implementer to the wrong bucket, wrong ARN pattern, or wrong capacity assumption. The 2026-06-09 audit scored Architecture 8/10 "memory matches code" — at the topology level it does not.
**Trade-off if fixed:** documentation-only change (DEFINITION/CLOSURE phase, product-engineer); zero runtime risk.
**Recommendation:** REJECT current memory as architecture truth. product-engineer must correct the five rows above, and add the standby model (H4/M10) and the dd-chain-capture supersession status (H5) as explicit ADRs.

### [HIGH] H4 — Availability posture: single-AZ public subnet + FARGATE_SPOT default + 1 Kinesis shard, undocumented
**Location:** `prd/02_vpc/network.tf:15-21` (one public subnet, one AZ); `prd/07_ecs/ecs.tf:49-55` (all 5 services pinned to that subnet, public IPs); `ecs.tf:15-23` (cluster default capacity provider `FARGATE_SPOT`); `prd/04_peripherals/peripherals.tf:93-100` (1 provisioned shard, 24 h retention).
**Issue:** the entire capture DAG shares one AZ and a spot-first capacity strategy; an AZ event or spot reclamation stops blocks/txs capture wholesale. The no-NAT/public-IP design is a legitimate cost decision, but neither it nor the single-AZ/spot consequences are recorded anywhere (`architecture.md` ADRs cover Kinesis-vs-Kafka, not availability).
**Why it matters:** Kinesis retention (24 h) bounds recovery: an outage longer than the SQS/Kinesis retention windows loses data the platform cannot reconstruct (Job 1 gap-recovery only works while the watcher itself runs).
**Trade-off if fixed:** a second public subnet + spreading services is nearly free; per-service spot/on-demand split is backlog `CAND-R2-02/05`. Full multi-AZ NAT-less design costs nothing extra for Fargate public-IP mode.
**Recommendation:** add a second public subnet in another AZ and distribute services; record an ADR "cost-over-availability: spot + single-AZ accepted until dd-chain-capture cutover" if that is the actual decision. Do not leave it implicit.

### [HIGH] H5 — Capture layer is superseded by dd-chain-capture but carries no deprecation decision; Kafka-era vestiges still wired into live infra
**Location:** ECS task definitions pass config-file argv that no job reads — `prd/07_ecs/ecs.tf:75-78,110-113,145-148,180-183,215-218` pass `/app/configs/producers.ini`/`consumers.ini`; no `configs/` dir exists in the image (`apps/docker/onchain-stream-txs/Dockerfile:18` copies only `src/`) and `1_mined_blocks_watcher.py:66-104` (and siblings) read env vars only. Kafka topic names live on in `5_txs_input_decoder.py:4-6`, `utils/src/dm_chain_utils/dm_kinesis.py:6-8` (which also mislabels Firehose streams as Kinesis), `dm_sqs.py:5-6`, `dm_cloudwatch_logger.py:6`, `alert_dynamodb_deadlock/resources/alerts/alert_dynamodb_deadlock.yml:6` ("tópico Kafka"), `prd/02_vpc/network.tf:63` ("MSK brokers"), `prd/07_ecs/ecs.tf:336` ("4 partições de mainnet.4"). The whole fleet is at `desired_count = 0`.
**Issue:** the sibling repo `dd-chain-capture` (VPS + Docker Swarm + Kafka + Redis, S3 as the integration boundary) replaces this entire layer — ECS jobs, SQS, Kinesis, Firehose, the DynamoDB SEMAPHORE/BLOCK_CACHE entities, and most of `dm-chain-utils` (`dm_sqs`, `dm_kinesis`, `dm_firehose`, `api_keys_manager`). Nothing in `specs/memory/` records this; `architecture.md` presents the capture layer as the live PRD design. Bug `drift-04-kafka-avro-dead-code` covers the source-level vestiges but not the architectural supersession.
**Why it matters:** this is precisely "evolving a feature on a rotted foundation": any new work invested in jobs 1–5, the ECS stacks, or the SQS/Kinesis modules is work on a layer scheduled for deletion. The dead argv in live task definitions also means the deployed containers and the Terraform that describes them already disagree about the contract.
**Trade-off if fixed:** an ADR + deprecation plan costs nothing now; deleting the layer is gated on dd-chain-capture cutover (operator holds VPS Phase-4). Premature deletion risks losing the rollback path.
**Recommendation:** record ADR-007 "capture layer superseded by dd-chain-capture; S3 raw layout is the frozen contract" in memory; freeze feature work on jobs 1–5; strip the dead argv from the task definitions next time `07_ecs` is touched; schedule deletion of SQS/Kinesis/Firehose modules + capture jobs for post-cutover.

### [HIGH] H6 — Provider lock files are gitignored: non-reproducible infrastructure across envs and time
**Location:** `.gitignore:48` (`**/.terraform.lock.hcl`); open-ended constraints `>= 5.0` (all new stacks), `>= 4.60.0` + `>= 1.36.0` (`prd/05*_databricks*/main.tf:5-12`).
**Issue:** every `terraform init` (CI run, operator laptop, env) is free to resolve a different AWS/Databricks provider version. The Databricks provider in particular changes resource behavior between minors (memory itself notes `genie_spaces` support varies by provider version).
**Why it matters:** "drift between envs" is guaranteed at the provider level even when `.tf` files are identical — HML can pass on provider X while PRD applies with provider Y. Combined with H1 (different codepaths), parity claims are hollow.
**Trade-off if fixed:** committing lock files adds upgrade-PR churn (dependabot-style bumps); that churn is the feature.
**Recommendation:** remove line 48 from `.gitignore`, commit `.terraform.lock.hcl` per stack, and pin upper bounds (`~>`) on both providers.

---

## 3. MEDIUM findings

### [MEDIUM] M1 — DEV state model: SPEC says local, code says remote S3
`specs/domains/infrastructure/SPEC.md:53` ("State local (gitignored) — nunca remoto") vs `services/dev/01_peripherals/main.tf:17-23` (S3 backend, key `dev/peripherals/...`) and `Makefile:416` ("Estado: S3 remoto"). One of them is lying; today the spec is. **Fix:** update the SPEC (remote state for dev is the better practice anyway).

### [MEDIUM] M2 — HML lifecycle contradiction: "100% ephemeral" spec vs persistent-resource code; phantom module; PRD coupling
`infrastructure/SPEC.md:58` claims HML is 100% ephemeral and lists module `01_tf_state_placeholder` — no such directory exists (`services/hml/` has 02,03,04,05,05b,07). `hml/04_peripherals/main.tf:5-6` states "Todos os recursos são persistentes... CI/CD cria apenas: ECS cluster + SG (efêmeros)". Worse, "ephemeral" HML depends on PRD account-level state: `hml/05_databricks/databricks.tf:126-129` resolves the **PRD-owned** metastore by name — HML cannot exist before PRD. **Fix:** rewrite the SPEC's HML section to the real model (persistent peripherals + ephemeral compute), delete the phantom module row, and document the metastore dependency in the deploy order.

### [MEDIUM] M3 — DABs config duplicated across 15 bundles; divergence already happened
Hardcoded workspace host `dbc-409f1007-5779.cloud.databricks.com` appears in every bundle's dev+hml targets; warehouse ID `a2a66f2adb0faf18` is a default in every dashboard/alert/genie bundle; operator e-mail is hardcoded as `run_as` in prod targets (`dashboard_network_overview/databricks.yml:10,17,24,29`; same pattern ×15). One env change = 15 edits, and C2 proves the copies have already diverged. ADR-004 (bundle atomicity) does not require duplicating env config. **Fix:** inject host/warehouse/catalog per target from CI (`--var` / env), or generate the `targets:` blocks from one source via the existing `beteugeuse` scaffolder.

### [MEDIUM] M4 — Prod catalog name drift: code says `prd`, memory says `dd_chain_explorer`
`prd/05b_databricks_workspace/databricks.tf:39-48` creates catalog `prd`; every bundle's prod target sets `catalog: "prd"`; `tech-stack.md:119-125` declares prod catalog = `dd_chain_explorer` (and `architecture.md:160` repeats it). **Fix:** correct memory (or rename the catalog — but memory must match whichever wins).

### [MEDIUM] M5 — genie_ethereum bundle is undeployable scaffolding
`apps/dabs/genie_ethereum/` is a full bundle, deployed by `Makefile:169-177` (phase 4), yet `architecture.md:149` records that `genie_spaces` is **not** a terraform-managed DABs resource in provider 1.88.0 (Genie created via UI). A bundle that cannot deploy its only resource is dead weight that will fail `dabs_deploy_all` or silently no-op. **Fix:** either gate it out of phase 4 with an explicit "manual-UI component" marker, or delete the bundle and keep the SQL/source under docs until provider support lands.

### [MEDIUM] M6 — Two ABI cache layers, one vestigial; dead IAM grants
Job 5 uses DynamoDB `ABICache` (`apps/docker/onchain-stream-txs/src/utils_decode/abi_cache.py`), yet the ECS task still sets `ABI_CACHE_DIR=/tmp/abi_cache` (`prd/07_ecs/ecs.tf:221`) feeding the **file-based** cache inside `utils/src/dm_chain_utils/dm_etherscan.py:45-58,253-262` — two caches for the same data, the file one ephemeral per container. IAM grants Secrets Manager `dm-chain-explorer-*` to both execution and task roles (`prd/03_iam/iam.tf:27-41,114-121`) but the apps read keys exclusively from SSM. **Fix:** decide one cache (DynamoDB) and remove the file path from `dm_etherscan` or stop wiring it; drop the Secrets Manager statements unless something actually reads secrets.

### [MEDIUM] M7 — Working-tree pollution: recursive build artifacts, binaries, caches, duplicate test trees
`apps/dabs/job_delta_maintenance/src/batch/dm_delta_maintenance/build/lib/.../build/lib/.../build/lib/.../build/lib/` — build outputs nested **four levels** (each `setup.py` build re-packaged the previous build's output: AI building on its own debris); `dist/*.whl` and `.egg-info` in `job_ddl_setup/src` and `job_delta_maintenance`; committed/resident `__pycache__/*.pyc` under `apps/docker/onchain-stream-txs/{src,test,tests}`; `.hypothesis/` at repo root (forbidden cache dir per workspace law); per-bundle `.databricks/` holding **terraform provider binaries and local tfstate** (`job_trigger_all/.databricks/bundle/*/terraform/…`); lambda zips inside terraform dirs (`services/dev/02_lambda/.lambda_zip/gold_to_dynamodb.zip`, `services/modules/cloudwatch_logs/.lambda_zip/cw_logs_transform.zip`); duplicate test roots `test/` (old `test_server.py`) vs `tests/unit/` (new suite from r5). **Fix:** purge build/dist/egg-info/pycache/.hypothesis from the tree, verify none are git-tracked (`git ls-files`), delete the obsolete `test/` dir, and keep `.databricks/` out of the tree via clean checkouts in CI.

### [MEDIUM] M8 — REST API specced (SPEC+PLAN+TASKS) with zero implementation, outside any release
`specs/domains/applications/rest-api/{SPEC,PLAN,TASKS}.md` exist; `apps/rest-api/` does not. PLAN/TASKS for unscheduled work masquerade as active artifacts. **Fix:** demote to a backlog candidate (PM-curated) and delete the orphan PLAN/TASKS, or attach to a real release.

### [MEDIUM] M9 — Kinesis encryption explicitly NONE in HML and PRD
`hml/04_peripherals/main.tf:162`, `prd/04_peripherals/peripherals.tf:98` (`encryption_type = "NONE"`). Public-chain data lowers confidentiality stakes, but it contradicts the repo's own posture (S3 AES256 everywhere, NFR-INF-002) and costs one line to fix. **Fix:** `encryption_type = "KMS"` with the AWS-managed key, or an ADR stating why not.

### [MEDIUM] M10 — Runtime capacity managed outside Terraform without a documented contract
All 5 ECS services: `desired_count = 0` + `lifecycle { ignore_changes = [task_definition, desired_count] }` (`prd/07_ecs/ecs.tf:244-353`); actual scaling lives in `scripts/prod_standby.sh` / `prod_resume.sh`; image deploys via `aws ecs update-service` in the workflow (`deploy_all_dm_applications.yml:838`). The pattern is defensible (standby cost control) but is recorded nowhere — memory claims live replicas (H3). **Fix:** document the standby/resume contract in memory and in `prd/07_ecs` headers, including who owns desired_count truth.

---

## 4. LOW findings

- **L1 — Stale comments/docstrings:** Kafka topic maps in `dm_kinesis.py:6-8` (also wrongly labels Firehose-only streams as Kinesis), `dm_sqs.py:5-6`, `dm_cloudwatch_logger.py:6`; `decode_inputs.md` referenced in `5_txs_input_decoder.py:18` does not exist; "MSK brokers" in `prd/02_vpc/network.tf:63`; old stack numbering in `Makefile:332-343`. Tracked partially by bug `drift-04`; sweep the rest.
- **L2 — `.gitignore` archaeology:** `mnt/airflow/*`, `mnt/rosemberg/*`, `swarm.secrets*`, `z_old/`, `valid/.env` (`.gitignore:26-42,63-65`) reference a predecessor project's tree. Misleads readers about what the repo contains. Prune.
- **L3 — Orphan ECR repo:** `aws_ecr_repository "batch"` (`onchain-batch-txs`, `prd/07_ecs/ecs.tf:371-381`) has no producer anywhere (the only push is commented out, `Makefile:315`). Delete or justify.
- **L4 — Versioned-name script duplication:** `scripts/hml_integration_test.sh` vs `scripts/hml_integration_test_optimized.sh` — the `_optimized` suffix is the classic stale-layer smell. Keep one.
- **L5 — Three naming patterns coexist:** `dm-chain-explorer-*` (roles, cluster), `dm-dd-chain-explorer-prd-*` (lambda roles, `deploy_all_dm_applications.yml:38-39`), `mainnet-*-prd` / `dm-{env}-firehose-*` (modules). FR-INF-004 names only two. Converge on next touch.
- **L6 — Dev compose mounts host `~/.aws` (`services/dev/00_compose/app_services.yml:13`)** — read-only and dev-only, acceptable, but worth an explicit comment that real credentials enter every container.
- **L7 — Manual post-apply step encoded as a comment:** `prd/04_peripherals/peripherals.tf:49-53` instructs deleting `.keep` objects by hand after apply (ISSUE-029). Manual steps in comments rot; encode in a script or accept the objects.
- **L8 — `specs/releases/legacy/SPEC.md`** floats outside `_archive/`; move it under `_archive/` with its peers (relates to bug `drift-05`).

---

## 5. Environment parity matrix (intentional vs accidental)

| Aspect | DEV | HML | PRD | Classification |
|---|---|---|---|---|
| Stacks | 00_compose, 01_peripherals, 02_lambda | 02_vpc, 03_iam, 04_peripherals, 05_databricks, 05b, 07_ecs | 01_tf_state, 02_vpc, 03_iam, 04_peripherals, **05_databricks (stale)** + 05a + 05b, 06_lambda, 07_ecs | PRD 05_databricks = **accidental (C1)** |
| TF codepath | modules (peripherals only) | shared modules (vpc/iam/ecs) | **inline hand-rolled** vpc/iam/ecs | **Accidental (H1)** |
| State backend | S3 remote (spec says local) | S3 remote | S3 remote + 01_tf_state bootstrap | Backend fine; **spec drift (M1)** |
| Firehose target | `dev-ingestion` `raw/` | `hml-lakehouse` `raw/` (but dlt_ethereum reads `hml-raw`) | `lakehouse` `raw/` (memory says `raw-data`) | HML reader = **accidental (C2)**; memory = **accidental (H3)** |
| Firehose buffers | 1 MB / 60 s | 1 MB / 60 s (intentional: fast tests) | logs 5 MB/300 s; data streams module defaults (backlog CAND-R2-03) | Intentional, partially tracked |
| DynamoDB PITR | false | false | true | Intentional (cost) |
| Kinesis encryption | module default | NONE | NONE | **Accidental (M9)** |
| Lambda | gold_to_dynamodb (TF) | none in TF (CI-side only) | contracts_ingestion + gold_to_dynamodb (TF) | Gap: lambda untested via HML terraform — verify CI covers it |
| ECS | docker compose, 12 containers | module cluster, ephemeral tasks via CI | inline cluster, 5 services at desired_count=0 (standby) | Standby intentional; **undocumented (M10)** |
| Databricks | shared workspace `dbc-409f1007` via DABs | TF creates MWS workspace; **DABs deploy to shared dev workspace** | MWS via 05a/05b, catalog `prd` | HML = **accidental split-brain (C2)**; catalog name = memory drift (M4) |
| Auth (Databricks) | PAT profile | OAuth env (TF) / hardcoded host (DABs) | OAuth M2M | Matches memory except HML DABs path |
| Lifecycle rules | expire 7d | expire 7/30d | IA 30d → Glacier 90d (raw), IA 90d (lakehouse) | Intentional (cost), diverges from r2 spec (tracked: drift-r2-s3-lifecycle-partial) |

---

## 6. Dead / legacy architecture inventory

| Item | Evidence | Disposition |
|---|---|---|
| `services/prd/05_databricks/` | C1 | DELETE (after state check) |
| Makefile targets `publish_apps`, `deploy_dev_all`, `tf_apply_remote_state`, `prod_destroy_infra` (broken), Databricks targets pointing at 05_databricks | H2 | DELETE / repoint |
| Kafka/MSK vestiges: dead `.ini` argv in ECS task defs, topic-name docstrings, MSK comment, alert "tópico Kafka" comment | H5, L1 | Strip on next touch; covered partially by bug drift-04 |
| Capture layer as a whole (jobs 1–5, SQS/Kinesis/Firehose modules, `dm_sqs`/`dm_kinesis`/`dm_firehose`/`api_keys_manager`) | superseded by dd-chain-capture; fleet at desired_count=0 | FREEZE now, ADR + delete post-cutover (H5) |
| ECR `onchain-batch-txs` | L3 | DELETE |
| `apps/docker/onchain-stream-txs/test/` (old test_server) | M7 | DELETE (superseded by `tests/unit/`) |
| `scripts/hml_integration_test.sh` (non-optimized twin) | L4 | DELETE one |
| Recursive `build/lib` ×4, `dist/`, `.egg-info`, `.pyc`, `.hypothesis/`, `.databricks/` provider binaries + tfstate, `.lambda_zip` zips | M7 | PURGE from working tree |
| `genie_ethereum` bundle | M5 | Gate or delete until provider support |
| `specs/domains/applications/rest-api/{PLAN,TASKS}` | M8 | Move to backlog |
| `.gitignore` predecessor-project entries | L2 | PRUNE |
| `specs/releases/legacy/` | L8 | Archive |
| Abandoned r2/r3/r4 capabilities | already inventoried in `specs/backlog/rebuild-abandoned-r2-r3-r4-capabilities.md` | No action here — backlog is the right home |

---

## 7. Gate verdicts

- **Root-cause gate:** N/A for bug fixes in this review (no release under review); however C2's bucket mismatch must be fixed at the source (bundle config model, M3), not by another one-off edit — a one-line patch without centralizing target config is a workaround that will recur.
- **Architecture-fidelity gate: REJECTED.** `specs/memory/architecture.md` and `specs/domains/infrastructure/SPEC.md` misrepresent the S3 raw topology, IAM scoping, resource naming, HML lifecycle/Databricks model, and ECS runtime state. Required corrections enumerated in H3, M1, M2, M4, M10. Until memory is corrected, no SPEC built on it should be approved.

## 8. Recommended sequence (highest leverage first)

1. **C2 bucket fix** (`dlt_ethereum/databricks.yml:53`) — one line, restores meaning to the HML gate.
2. **C1 stale-stack deletion** (`prd/05_databricks` + Makefile/script repointing) — removes the split-brain control plane.
3. **H3/M1/M2/M4/M10 memory + SPEC corrections** (product-engineer, DEFINITION/CLOSURE phase) — restores the planning contract.
4. **H5 ADR-007 capture-layer supersession** — freezes investment in the dying layer.
5. **H2 Makefile purge**, **H6 lock files**, **M7 tree purge** — hygiene wave, mostly deletions.
6. **H1 codepath convergence + M3 DABs config centralization** — the structural projects; scope as a release.
