# SPEC — Release v0.7.0 — Market-data restart: batch capture runtime + batch medallion; Ethereum lane retired

> **Status:** Aprovado
> **Release ID:** v0.7.0
> **Owner:** product-engineer — approved under the operator standing order of 2026-09-13 ("faça tudo que puder, avance") after the operator ratified grill rulings R1-R17
> **Created / Approved:** 2026-09-13
> **Amended:** 2026-09-23 — R18-R26 (§11): batch Job on file arrival, Ethereum destroyed via IaC/CI, zero-manual chain + DEV e2e as gates; AC-11..14, 16 superseded. **(2)** R27-R36: Free Edition abandoned; serverless DEV + PROD workspaces; us-east-1, SSE-S3, S3 locking; I12-I15, AC-25..30 added; AC-7, 20, 23 amended.
> **Lifecycle:** v0.6.0 stays the live release until its C-DAY; v0.7.0 is pre-staged and becomes ACTIVE when v0.6.0 closes. `releases/ACTIVE.md` untouched.
> **Consumes:** market-data-medallion-restart, batch-medallion-and-ethereum-retirement, cicd-zero-manual-steps, e2e-dev-validation-financial-lakehouse, databricks-serverless-us-east-1-migration, capture-ecr-state-and-kms-ownership-transfer
> **Provenance:** grill handoff `2026-09-13T011657Z-project-manager-restart-audit-grill` (R1-R17) · operator rulings 2026-09-23 R18-R26 and R27-R36 (the three backlog entries above; serverless cost study) · architect DRAFT `dd-chain-infrastructure/docs/design/batch-capture-runtime.md` · capture atoms `batch-capture-lane`, `raw-landing-contract`
> **Scope (operator-locked):** e2e proven in DEV (R4); PRD gets its platform, no workload (R27-R28). WS-I — runtime, region move, Databricks/GitHub stacks, infra halves of teardown and chain; WS-X — one batch bundle + explorer halves. Detail: `PLAN.md`.

## 1. Problem

`dd-chain-capture` v0.5.0 shipped three images (`b3-market-data`, `cvm-open-data`,
`bcb-sgs`), seven jobs and the raw contract (untouched bytes under
`raw/<source>/<dataset>/ingest_date=YYYY-MM-DD/` + `_manifest.json` `raw-manifest-v1`
written last); nothing ran them or read that layout. **(a)** Deploy roles grant no
`scheduler:` (a hand-kept-policy bug family). **(b)** The UC stack sat outside CI. **(c)** DLT
never ran and is not wanted (R19). **(d)** The parked Ethereum lane holds live objects (R21).
**(e)** Every DEV step was a hand command (M1-M15). **(f)** Free Edition refuses compute and
metastore grants, forcing hand-made UC objects (R27); sa-east-1 costs ~25.7% more (R29).

## 2. Scope — IN

Write sets by repository: WS-I → `dd-chain-infrastructure` (+ the capture region literal,
I12); WS-X → the new `dd-chain-explorer`; WS-O → operator acts only; all on `feature/0.7.0`.

### 2.1 WS-I — `dd-chain-infrastructure`

| # | Goal |
|---|---|
| I1 | **Bug first.** Register `deploy-roles-lack-scheduler-grants-for-declared-schedule`; add `test_every_aws_service_namespace_declared_in_services_is_granted` (deploy + read-only Allow per `aws_<svc>_*`; every `Principal.Service` in `ProjectIamPassRole`) RED on `scheduler`, GREEN after I2. |
| I2 | **Bootstrap delta** (`prd/00_bootstrap`): role `gha_capture_publish` (OIDC to capture envs `dev`/`production`, ECR push/pull on the three repos); statements per PLAN §3.2; `s3:HeadObject` deleted; `publish_oidc_vars.sh --target infra\|explorer\|capture`. |
| I3 | **ECR ×3** in `prd/04_peripherals`: `dm-chain-explorer-capture/<image>`, MUTABLE, scan on push, `force_delete`, lifecycle; `empty_s3_and_ecr.sh` → `empty_s3_buckets.sh`. |
| I4 | **Buckets** `dm-chain-explorer-<env>-<purpose>`, dev/prd × `raw-data`/`lakehouse` (R32): PAB, SSE-S3; raw `INTELLIGENT_TIERING` day 0, **no expiration**; MFA-gated dev writer role (no delete). |
| I5 | **Stack `dev/03_capture`**: Fargate/Spot, egress-only SG in the default VPC, one task role per image scoped to `raw/<source>/*`, three task definitions, **seven schedules `DISABLED`**; runbook `capture-backfill.md`. |
| I6 | *(superseded by I14)* UC stack of three objects over a hand-made catalog. |
| I7 | **Map-driven CI**: `stack_map.json` drives one `dev-deploy` job and the plan/drift/destroy workflows; **`detect_changes.sh` deleted**. |
| I8 | **Contract tests** (PLAN §3.4): namespace coverage, publish-role minimality, images equality, schedules `DISABLED`, prefix-scoped task roles, dev-lane order. |
| I9 | **Words and version.** Capture code in `dd-chain-capture`, runtime here; no `vars.ECR_REGISTRY`; `VERSION` `0.7.0`. |
| I10 | **Ethereum AWS surface destroyed through the lanes (R21, O-10).** dev: `s3_ingestion`, `dynamodb`, `dev/02_lambda`; prd: `06_lambda` (Lambdas, layer, notification, schedule), `dynamodb`, the lambda seam's infra half (`s3_artifacts`, `gha_artifacts_publish`, `resolve_*`; R23) behind the prd gate. Free Edition objects are abandoned with that org (R27). |
| I11 | **Zero-manual chain, infra half.** A `develop` merge runs infra apply → explorer deploy signal → one Fargate capture run (M14); plan-as-detector, no `force_apply` (M11); cross-repo order by events (M12). **Trust seed**, one idempotent script + runbook per account: S1 bootstrap (+ new tf-state bucket), S2 GitHub App (R26), S3 account-SP secret. |
| I12 | **Region move (R29, R32-R34).** One `aws_region` variable + workflow `AWS_REGION` = `us-east-1`; every `sa-east-1` literal replaced (infra; capture `publish-images.yml` + its test). New tf-state bucket, `use_lockfile = true`; DynamoDB lock table, its grants, `tf_state_lock_check.sh` deleted. First, CI destroys the sa-east-1 stacks (`prevent_destroy` lifted in that commit, buckets emptied) and the orphan `capture/ecr` state whole — 11 resources incl. KMS, Roles Anywhere (R34). |
| I13 | **Account stack `services/account/databricks`** (R27, R31): account provider, account SP by OAuth M2M; one us-east-1 metastore; two `SERVERLESS` workspaces `dm-chain-explorer-dev`/`-prd` + metastore assignment; one deploy SP per env with secret and workspace permission assignment; budget alert. |
| I14 | **Per-workspace UC stack `services/<env>/04_unity_catalog`**, rebuildable from git (R28, R31, R36): storage credential on the us-east-1 UC role (UCMasterRole + self-assume + ExternalId trust, file-event permissions), **file events on**; external locations raw (read-only) + lakehouse (RW); catalog `dev`/`prd` **ISOLATED**, bound to its workspace, `storage_root` on its lakehouse bucket; grants to account identities; DEV one SQL warehouse 2X-Small, auto-stop 1 min, max 1 cluster; PROD none; outputs host + warehouse id. |
| I15 | **GitHub stack** (`github` provider, App auth; R35): environments, secrets and variables (host, SP client id/secret, account id), default branch `develop` in infra + explorer (M3-M6, M10, M15). |

**Write set:** the infra repo, its state keys, the capture region literal + test; live AWS,
the Databricks account and workspaces, GitHub settings. **Non-goals:** §3.

### 2.2 WS-X — `dd-chain-explorer`: bundle `job_market_data`

| # | Goal |
|---|---|
| X1 | **One bundle `apps/dabs/job_market_data/`** (R19): target `dev` real (dev SP `run_as`, `[dev] ` prefix, catalog `dev`), `prod` validated, never deployed here (catalog `prd`); host from the GitHub environment; tables by `LOCATION` on an external location; `performance_target: STANDARD`; `artifact_path` on a UC volume; **one serverless job `dm-market-data`, three chained PySpark batch tasks `bronze → silver → gold`**, Delta only; no `pipelines:`, no `dlt` import. |
| X2 | **Parsers reused, not rewritten**: `dm_market_parsers` (pure Python, tested off-cluster) moves with the bundle unchanged. |
| X3 | **Bronze `b_market`** — every partition whose `_manifest.json` sha256 is not yet in `raw_manifests`: one table per dataset (11, §6) of undecoded bytes (`binaryFile`) + `source, dataset, ingest_date, file_name, content_sha256, _ingested_at`, and `raw_manifests` (explicit schema); MERGE on `content_sha256` — a rerun adds nothing (R13). |
| X4 | **Silver `s_market`** — 8 tables (§6, PLAN §4.3), MERGE on each natural key. Parse failure, `content_sha256 ∉` the partition manifest, `versao IS NULL` → rejected and counted, never coerced. `cvm_statements` = DFP + ITR `{BPA,BPP,DRE,DFC_MI}_con`, `vl_conta × ESCALA_MOEDA`, **max `VERSAO` per (cnpj, dt_refer, statement, grupo_dfp), `ORDEM_EXERC = ÚLTIMO`**. FRE/IPE/trade-information bronze-only. |
| X5 | **Gold `g_market`** — 3 tables by overwrite: `company_daily_price` (market cap via `cvm_fca_securities`; NULL never fabricated); `ibov_constituents_daily`; `company_fundamentals_snapshot` (TTM, EBITDA = EBIT + D&A, `pl pvp ev_ebitda roe roic margins dl_ebitda`; `dy` NULL deferred; banks EBITDA NULL; no CAGR). |
| X6 | **File-arrival trigger (R20)** on a new `_manifest.json` under the dev raw external location (file events, R36); `UNPAUSED` in `dev`; `max_concurrent_runs: 1`; no cron, no CI-started run. |
| X7 | **Tests, docs.** Parser suite kept; bundle contract → exactly **1** bundle (1 job, 3 ordered tasks, serverless, file-arrival); no-`dlt`-import contract; seam 3 kept in `docs/cross-repo-contract.md`; README one bundle; versions `0.7.0`. |
| X8 | **Ethereum and DLT code deleted (R21, R27)** — nothing to destroy, those bundles live only in the abandoned org: the eight dirs (`dlt_market_data`, `dlt_ethereum`, `dlt_app_logs`, `job_export_gold`, four dashboards), `apps/lambda/`, `utils/`, `publish-artifacts.yml` (R23), dashboard tooling, their tests. |
| X9 | **Zero-manual chain, explorer half.** The infra signal deploys the bundle to `dev` with no hand filter (M11); the first run is a file-arrival fire (M13). |

**Write set:** the new `dd-chain-explorer`; live `dev` (this bundle); `specs/**` where
authority is (O-9). **Non-goals:** §3.

### 2.3 WS-O — operator-only surface

Seed S1-S3 (the only manual apply, MFA) and environment approvals; the constitution
amendment. Any other hand act is an M-step.

## 3. Scope — OUT

| Out of scope | Reason |
|---|---|
| PRD capture runtime, PRD bundle deploy, `schedules_enabled = true` | R4; `prod-environment-official-account` residual |
| Digest-resolved images; managed VPC/NAT | Q3; budget |
| CMK / KMS keys | R30 — study `encryption-at-rest-posture-decision` |
| DLT in any form | R19 — re-entry needs a ruling |
| DY, payout, CAGR, dashboards, Genie; FRE/IPE silver; Basel ratio | R11; `financial-sources-expansion-data-model` |
| Any Ethereum capability; objects left in the Free Edition org | R21; R27 |
| `terraform-single-stack-tree-per-env-tfvars`; `dadaia-agents` | R10; owned elsewhere |

## 4. Acceptance criteria

`<raw-bucket>` = `dm-chain-explorer-dev-raw-data`; no account id, host or personal
identifier in any evidence (public repository).

| AC | WS | Verification | Pass condition |
|---|---|---|---|
| AC-1 | I | `pytest -k namespace` at the I1, then the I2 commit | RED naming `scheduler`, then GREEN; bug `resolved` |
| AC-2 | I | plan of `00_bootstrap`; `simulate-principal-policy` on `gha_capture_publish` | 1 role added, 0 destroyed; `ecr:PutImage` on a capture repo allowed; other repos, `s3:PutObject`, `ecs:RunTask`, `iam:PassRole` denied |
| AC-3 | I | `gh variable list` in `dd-chain-capture` | `AWS_CAPTURE_PUBLISH_ROLE` set by code or seed; no `ECR_REGISTRY` |
| AC-4 | I | `ecr describe-repositories`, `get-lifecycle-policy` (us-east-1) | three capture repos, MUTABLE, scan on push, both rules |
| AC-5 | I | bucket probes; writer role `simulate-principal-policy` | 4 buckets in us-east-1; raw IT day 0, **no `Expiration`**; four blocks `true`; MFA trust; `PutObject raw/*` allowed, delete and other buckets denied |
| AC-6 | I | CI plan of `dev/03_capture`; `scheduler list-schedules` | 3 task definitions on `<ecr-url>:dev`; SG no ingress; 7 schedules `DISABLED` |
| AC-7 | I | UC plan per env before/after CI apply; `grants get-effective`; `external-locations validate`; `catalogs get` | adds, then `No changes`; SP privileges effective; both locations validate; catalog `ISOLATED`, bound to its workspace; file events on *(amended: was 3 creates)* |
| AC-8 | I | `pytest scripts/ci/tests` in CI; `grep` workflows; `ls scripts/ci` | green, I8 collected; one `dev-deploy` job; no `detect_changes.sh`; map stacks in drift + destroy-all; `actionlint` + `zizmor` clean |
| AC-9 | I | fresh-clone `terraform plan` of every CI stack in `stack_map.json`, OIDC | `0/0/0` each |
| AC-10 | I | `grep -rn 'own VPS\|Nothing in this repository captures\|HeadObject\|ECR_REGISTRY\|detect_changes'`; `cat VERSION` | 0 hits; `0.7.0` |
| AC-15 | X | read `docs/cross-repo-contract.md`, `apps/dabs/README.md`; versions `sort -u` | seam 3 stated once; lambda seam and Ethereum rows gone; `0.7.0` |
| AC-17 | O | `git diff specs/constitution.md` | §1 image seam in, lambda seam out; §2 two serverless workspaces (dev, prd), Free Edition + `hml` out, DynamoDB clause out; §6 UC path; §7 batch raw layout + `Market data` row, Ethereum row and `@dlt` rule out; §10 classification row |
| AC-18 | V | each changed repo's `feature/0.7.0` → `develop` PR; secret scan; trio | green after v0.6.0's merge; 0 findings; qa, code, security APPROVED per repo |
| AC-19 | X | `ls apps apps/dabs`; `pytest tests` without `pyspark`; `grep -rnE '(import\|from) dlt\|@dlt\.' apps tests` | one bundle `job_market_data`; no `apps/lambda`, no `utils/`; contract: 1 job, `bronze → silver → gold`, serverless, file-arrival; parser fixtures (COTAHIST `preult` ÷100, 244-char line rejected, Latin-1 round-trip, VERSAO max, YTD differencing); grep 0 |
| AC-20 | X | `bundle validate -t dev` and `-t prod` | exit 0 both, hosts from environments; prod not deployed *(amended)* |
| AC-21 | X | `bundle summary -t dev`; `jobs get`; `pipelines list`; SP `.bundle/` | one job `[dev] dm-market-data`, 3 tasks, serverless, `file_arrival` `UNPAUSED`; 0 pipelines; `.bundle/` holds this bundle only |
| AC-22 | X | **the POC gate** — CLOSURE table, one `ingest_date` per image landed by a workflow-run Fargate task | raw keys + manifest sha256; trigger = file arrival; `SHOW TABLES` 12 / 8 / 3; rows per layer, every `g_market` table > 0; 0 sha rejections; a second fire changes no count |
| AC-23 | E | AWS probes (bucket, DynamoDB, Lambda, schedule, artifacts role); `stack_map.json`; `grep -rniE 'ethereum\|etherscan\|dynamodb'` explorer `apps tests .github`, infra `services scripts .github` | R21 objects and the lambda seam absent in every region; no `lambda` stack; each removal cites a CI run id; grep 0 *(amended: Free Edition probes dropped)* |
| AC-24 | C | CLOSURE M-ledger table; the chain's run list; seed run twice | every M-step → workflow + job, seed step, or retired one-off, none `manual`; one chain from a `develop` merge yields AC-22 with every run event ∈ push / workflow_run / repository_dispatch / file arrival, human acts only environment approvals; second seed run = no changes, no secret echoed; drift on `develop` = 0 |
| AC-25 | I | `grep -rn sa-east-1` in infra, capture, explorer (excl. `docs/legacy`); backends | 0 hits; every backend us-east-1 with `use_lockfile = true`, no `dynamodb_table`; no `tf_state_lock_check.sh` |
| AC-26 | I | `resourcegroupstaggingapi get-resources --region sa-east-1`; `s3api list-buckets` + `get-bucket-location`; `kms list-aliases`; state keys | no project resource in sa-east-1; no `dd-chain-capture-ssm` alias, no Roles Anywhere anchor; `capture/ecr` key gone; each destroy cites a CI run id |
| AC-27 | I | `get-bucket-encryption` on every project bucket; `grep -rnE 'aws_kms_key\|kms_master_key_id\|aws:kms' services` | `AES256` everywhere; grep 0 |
| AC-28 | I | `account workspaces list`; `metastores list`; GitHub env secret/variable names | 2 workspaces `RUNNING`, serverless, us-east-1, one metastore; env secrets written by the GitHub stack; default branch `develop` in infra + explorer |
| AC-29 | V | **rebuild drill** (R28): CI destroy + re-apply of the dev per-workspace stack, then bundle redeploy, from git | no hand act; same `SHOW TABLES` 12/8/3 and row counts per table before/after; no lakehouse object deleted; next file arrival fires the job |
| AC-30 | C | CLOSURE cost table | per line item, sa-east-1 vs us-east-1 list price for the reference workload (Databricks, AWS, total %); `system.billing.usage` × list price over the first 7 days vs the sa-east-1 estimate; measured % saving stated |

**Superseded (not evidence):** AC-11 → AC-19 · AC-12 → AC-20 · AC-13 → AC-21 · AC-14 →
AC-22 · AC-16 (hand smoke + `run-task`, = M14) → AC-22/AC-24.
**Ship gate:** AC-1..10, AC-15, AC-17..30 green; memory (§9); CLOSURE; promote-or-continue is
the operator's.

## 5. Ordering safety

| # | Rule |
|---|---|
| O-1 | **v0.6.0 first (R5).** `feature/0.7.0` stacks on `feature/0.6.0` and merges into `develop` after v0.6.0's merge. |
| O-2 | **Bug before fix.** Bug record and RED test land before any grant. |
| O-3 | **Bootstrap → registry → images → runtime**; schedules stay `DISABLED`. |
| O-4 | **Account stack → bucket → UC stack → bundle.** |
| O-5 | **Every UC object is owned by a stack**; nothing hand-made (R28). |
| O-6 | **Real bytes before the first run** — partitions landed by the images, never fixtures in the real bucket. |
| O-7 | **PRD = platform only**; `prod` target validated, never deployed; no PRD destroy path — resilience is proven on DEV (AC-29). |
| O-8 | **Secrets are never copied.** Typed once into the seed or published by it; agents reference names. |
| O-9 | **Specs write where authority is** — the legacy tree until v0.6.0's C-DAY, the new explorer after. |
| O-10 | **Destroy before delete.** Every deployed object is destroyed by CI while its source exists; the source dies in a later commit; nothing is removed from a laptop (M9 not repeated). |
| O-11 | **Seed once, workflows for the rest.** An act no workflow reproduces is a seed step or an open M-step, appended the day it happens. |
| O-12 | **Teardown before bring-up.** sa-east-1 is destroyed by CI before any us-east-1 apply reuses a bucket name. |

## 6. The dataset contract — raw → bronze → silver → gold

Raw partition `raw/<source>/<dataset>/ingest_date=YYYY-MM-DD/`; B bronze, S silver, G gold
consumer (X5).

| Dataset | Format | B | S | G |
|---|---|---|---|---|
| `b3/cotahist` | ZIP → fixed-width 245-char records | `b3_cotahist` | `b3_quotes` | price, fundamentals |
| `b3/ibov_portfolio` | JSON pages | `b3_ibov_portfolio` | `b3_ibov_portfolio` | constituents |
| `b3/instruments_consolidated` | `;` Latin-1 CSV, status line | `b3_instruments_consolidated` | `b3_instruments` | bridge (ISIN, governance) |
| `b3/trade_information_consolidated` | `;` Latin-1 CSV, status line | `b3_trade_information_consolidated` | — | — |
| `cvm/cad_cia_aberta` | `;` Latin-1 CSV | `cvm_cad_cia_aberta` | `cvm_companies` | dimensions |
| `cvm/fca` | yearly ZIP of `;` Latin-1 CSVs | `cvm_fca` | `cvm_fca_securities` | bridge (ticker ↔ CNPJ) |
| `cvm/dfp`, `cvm/itr` | yearly ZIPs of `;` Latin-1 CSVs | `cvm_dfp`, `cvm_itr` | `cvm_statements`, `cvm_capital_composition` | fundamentals, price |
| `cvm/fre`, `cvm/ipe` | yearly ZIPs of `;` Latin-1 CSVs | `cvm_fre`, `cvm_ipe` | — (next candidate) | — |
| `bcb/sgs` | JSON per series | `bcb_sgs` | `bcb_series` | context only |
| `_manifest.json` (every partition) | `raw-manifest-v1` JSON | `raw_manifests` | join key `content_sha256` | — |

**Glossary.** *source, dataset, partition, manifest* — capture's `raw-landing-contract`;
**capture runtime** — cluster, task definitions, schedules; **image seam** — the ECR registry
fed by capture CI (seam 3); **trust seed** — the one scripted, idempotent operator act per
account (S1-S3); **M-step** — one hand act in the `cicd-zero-manual-steps` ledger;
**per-workspace stack** — the UC stack a workspace is rebuilt from (AC-29).

## 7. Bugs and backlog

- **Consumed** (`picked (v0.7.0)`, LEDGER at CLOSURE): `market-data-medallion-restart`,
  `batch-medallion-and-ethereum-retirement`, `cicd-zero-manual-steps`,
  `e2e-dev-validation-financial-lakehouse`, `databricks-serverless-us-east-1-migration`,
  `capture-ecr-state-and-kms-ownership-transfer` (R34).
- **Exit at CLOSURE `REJECTED · obsolete-by-R21`:** `dlt-ethereum-data-quality-enhancements`,
  `dashboards-analytics-enrichment`, `s3-raw-lifecycle-intelligent-tiering`,
  `rest-api-public-endpoint`. `encryption-at-rest-posture-decision` stays ACTIVE as the R30 study.
- **Picked bug:** `deploy-roles-lack-scheduler-grants-for-declared-schedule` — T-I7.1/T-I7.2.

## 8. Execution model

**(a)** trio · **(b)** runtime → AC-1..10 · **(c)** code + CI, nothing live → AC-19, 20, 25,
27 · **(d)** sa-east-1 + Ethereum teardown via CI → AC-23, 26 · **(e)** us-east-1 bring-up:
seed, one `develop` push → AC-4..7, 21, 22, 28 · **(f)** AC-24, 29, 30 · **ship:** AC-18;
memory → CLOSURE → merges; promote-or-continue.

## 9. Memory files affected at CLOSURE (do NOT write now)

- `architecture.md` — ADR-002 + ADR-10's Free Edition half superseded (R27); new ADRs: serverless DEV + PRD in us-east-1, isolated catalogs; image seam + CI-applied UC stacks; batch Jobs (R19); Ethereum + lambda seam retired (R21); SSE-S3 + S3 locking; ADR-003 deleted.
- `tech-stack.md` — Fargate/Spot, ECR, Scheduler, serverless workspaces in; Lambda, DynamoDB, DLT, KMS out.
- `product/`: `capture-layer` (images, jobs, raw contract); `medallion-pipelines`, `data-catalog` (`job_market_data`, 12/8/3, `dev`/`prd`); `serving-layer` (SQL over `g_market`); `aws-resources`, `cicd-pipeline` (us-east-1, stacks, lock, seed, chain); `index`, `catalog.json`.
- `quality-assurance.md` — parser suite, namespace family, 1-bundle + no-`dlt`, rebuild drill; `constitution.md` — T-O7.5 (AC-17).

## 10. Dependencies & risks

| Risk / dependency | Mitigation |
|---|---|
| **New account spend** (card-billed) | budget alert (I13); DEV 2X-Small, 1-min auto-stop; PRD no warehouse; AC-30 |
| **Account SP is account admin** | secret only via seed S3 → GitHub secret; never in the tree |
| **Bucket name reuse** after the sa-east-1 delete | O-12; buckets verified empty 09-23; lane retries |
| **Cross-repo credential; bootstrap needs MFA; C-DAY** | GitHub App, no PAT (R26); seed S1; O-9 |
| **Mutable `:dev`; Spot interruption** | schedules `DISABLED`; digest in the manifest; manifest-last + idempotent MERGE |
| **Layout/encoding drift; bank/D&A codes** | parsers reject, never coerce; ratios NULL without inputs |

## 11. Decisions resolved

**R1-R17** (grill 2026-09-12/13, full text in the handoff): ~~R1 Ethereum parked~~ (→ R21) ·
**R4** dev first · **R5** v0.6.0 first · **R9** SP grants in the UC stack · **R11** three images
/ seven jobs · **R12** ECR + narrow publish role · **R13** raw = untouched bytes + manifest ·
**R14** no expiry, IT · **R15** B3 daily 00:30 UTC, CVM weekly, BCB daily, floor 2010. **PM:**
Q1 ECR in `prd/04` · Q3 mutable `:dev` · Q5 constitution = OPERATOR-ONLY.

**R18-R26 (operator, 2026-09-23).** ~~**R18** Free Edition = DEV only~~ (struck by R27) ·
**R19** no DLT: one serverless job, three PySpark batch tasks · **R20** file-arrival trigger ·
**R21** Ethereum destroyed everywhere via IaC/CI · **R22** all inside v0.7.0 · **R23** lambda
seam deleted · **R24** `job_market_data` · **R25** ECR `stream`/`connect` via their owning
state (→ R34) · **R26** GitHub App chaining; no PAT.

**R27-R36 (operator, 2026-09-23).** **R27** retire ADR-10/R18 — Free Edition abandoned,
DEV + PROD = serverless workspaces in the operator's existing (empty, Premium, card-billed)
Databricks account · **R28** PROD permanent + rebuildable (drill), no destroy strategy · **R29**
region us-east-1 for everything incl. state, list-price saving ~25.7% (Databricks −25%, AWS
−38%) to be measured at CLOSURE · **R30** SSE-S3 only, no CMK — cost×security trade-off to be
studied later (`encryption-at-rest-posture-decision`) · **R31** one us-east-1 metastore,
catalogs dev/prd ISOLATED, storage_root on per-env lakehouse bucket, external tables only ·
**R32** new bucket names `dm-chain-explorer-<env>-<purpose>` + new tf-state bucket, sa-east-1
buckets (verified empty 2026-09-23) deleted via CI · **R33** S3-native TF locking
(`use_lockfile`), DynamoDB lock table removed · **R34** orphan `capture/ecr` state destroyed
entirely (11 resources incl. KMS + Roles Anywhere) — closes
`capture-ecr-state-and-kms-ownership-transfer` · **R35** `develop` default branch in infra +
explorer · **R36** file events enabled on the storage credential.
