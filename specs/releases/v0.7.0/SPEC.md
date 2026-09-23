# SPEC — Release v0.7.0 — Market-data restart: batch capture runtime + batch medallion; Ethereum lane retired

> **Status:** Aprovado
> **Release ID:** v0.7.0
> **Owner:** product-engineer — approved under the operator standing order of 2026-09-13 ("faça tudo que puder, avance") after the operator ratified grill rulings R1-R17
> **Created / Approved:** 2026-09-13
> **Amended:** 2026-09-23 — operator rulings R18-R22 (§11): the DLT medallion (old X1-X7) becomes one batch Databricks Job fired by file arrival; the Ethereum lane is destroyed everywhere through IaC/CI; the zero-manual CI/CD chain and the DEV end-to-end run are closure gates. AC-11..14 and AC-16 superseded (§4).
> **Lifecycle:** v0.6.0 stays the live release until its C-DAY; v0.7.0 is pre-staged and becomes ACTIVE when v0.6.0 closes. `releases/ACTIVE.md` untouched.
> **Consumes:** market-data-medallion-restart, batch-medallion-and-ethereum-retirement, cicd-zero-manual-steps, e2e-dev-validation-financial-lakehouse
> **Provenance:** grill handoff `2026-09-13T011657Z-project-manager-restart-audit-grill` (R1-R17) · operator rulings 2026-09-23 R18-R22 (backlog `batch-medallion-and-ethereum-retirement`, `cicd-zero-manual-steps`) · architect DRAFT `dd-chain-infrastructure/docs/design/batch-capture-runtime.md` · capture v0.5.0 `CLOSURE`, atoms `batch-capture-lane`, `raw-landing-contract` · source study Part C
> **Scope (operator-locked):** dev only (R4, R18). WS-I — the runtime that runs the three capture images and lands their bytes, plus the infra half of the Ethereum teardown and of the automated chain; WS-X — one batch medallion bundle over that landing, plus the explorer halves. No PRD resource is created; PRD Ethereum resources are destroyed through the prd lane. Detail: `PLAN.md`.

## 1. Problem

`dd-chain-capture` v0.5.0 shipped three images (`b3-market-data`, `cvm-open-data`,
`bcb-sgs`), seven jobs and the raw contract (untouched bytes under
`raw/<source>/<dataset>/ingest_date=YYYY-MM-DD/` + `_manifest.json` `raw-manifest-v1`
written last); nothing ran them, received their bytes, or read that layout. **(a)** The
deploy roles grant no `scheduler:` although `prd/06_lambda` declares a schedule — fifth of a
bug family (hand-kept policy, no test tying it to `services/**`). **(b)** The UC stack sat
outside CI, so R9 could not land through CI. **(c)** The DLT pipeline never ran (09-21) and is
not the processing model wanted (R19). **(d)** The parked Ethereum lane still holds live
objects, code and grants with no consumer (R21). **(e)** Every step that reached DEV was a hand
command (M1-M15, `cicd-zero-manual-steps`) — a green run reached by hand is not delivered.

## 2. Scope — IN

Write sets are disjoint by repository: WS-I → `dd-chain-infrastructure`, WS-X → the new
`dd-chain-explorer`, WS-O → operator acts only; both on `feature/0.7.0` (O-1).

### 2.1 WS-I — `dd-chain-infrastructure`

| # | Goal |
|---|---|
| I1 | **Bug first.** Register `deploy-roles-lack-scheduler-grants-for-declared-schedule`; add `test_every_aws_service_namespace_declared_in_services_is_granted` (deploy + read-only Allow per `aws_<svc>_*`; every `Principal.Service` in `ProjectIamPassRole`) RED on `scheduler`, GREEN after I2. |
| I2 | **Bootstrap delta** (`prd/00_bootstrap`): role `gha_capture_publish` (OIDC to capture envs `dev`/`production`, ECR push/pull on the three repos); statements per PLAN §3.2; `s3:HeadObject` deleted; `publish_oidc_vars.sh --target infra\|explorer\|capture`. |
| I3 | **ECR ×3** in `prd/04_peripherals`: `dm-chain-explorer-capture/<image>`, MUTABLE, scan on push, `force_delete`, lifecycle; `empty_s3_and_ecr.sh` → `empty_s3_buckets.sh`. |
| I4 | **Dev raw landing** in `dev/01_peripherals`: `dm-chain-explorer-dev-raw-data` (PAB, SSE-S3, `INTELLIGENT_TIERING` day 0, **no expiration**); MFA-gated writer role (no delete); `databricks_dev_s3_policy` widened. |
| I5 | **Stack `dev/03_capture`**: Fargate/Spot, egress-only SG in the default VPC, one task role per image scoped to `raw/<source>/*`, three task definitions, **seven schedules `DISABLED`**; runbook `capture-backfill.md`. |
| I6 | **UC stack** `services/dev/04_unity_catalog`: external location `dm-dev-raw-data`, two singular `databricks_grant` for the dev SP; exactly three creates. |
| I7 | **Map-driven CI**: `stack_map.json` drives one `dev-deploy` job and the plan/drift/destroy workflows; **`detect_changes.sh` deleted**. |
| I8 | **Contract tests** (PLAN §3.4): namespace coverage, publish-role minimality, images equality, schedules `DISABLED`, prefix-scoped task roles, schedule ↔ container, dev-lane order. |
| I9 | **Words and version.** Capture code lives in `dd-chain-capture`, the runtime here; no `vars.ECR_REGISTRY`; `VERSION` `0.7.0`. |
| I10 | **Ethereum AWS + UC surface destroyed through the lanes (R21, O-10).** dev: modules `s3_ingestion` (`dm-dev-ingestion`) and `dynamodb` leave `dev/01_peripherals`; `dev/02_lambda` destroyed by the destroy lane, then removed from code and `stack_map.json`. prd: `06_lambda` (both Lambdas, layer, notification, schedule `dm-dd-chain-explorer-prd-contracts-ingestion-hourly`), the prd `dynamodb` module and the lambda seam's infra half (`s3_artifacts`, `gha_artifacts_publish`, `resolve_*` scripts; §11) destroyed through the prd lane gate. Objects no state here owns — UC external location `dm-dev-ingestion`, the seven Ethereum schemas, ECR `stream`/`connect` — removed by one idempotent CI **retirement job**. Lambda/DynamoDB grants leave the bootstrap at the next seed run. |
| I11 | **Zero-manual chain, infra half.** A `develop` merge runs infra apply → signals the explorer deploy → one Fargate capture run as a workflow step (M14); change detection right on push and dispatch, no `force_apply` (M11); drift runs on the deploy branch (M15); GitHub environments/variables/secrets declared in code or emitted by the seed (M3-M5); cross-repo order by events, never a hand rerun (M10, M12). **Trust seed** — one idempotent script + runbook, once per account: bootstrap apply, Databricks SP + secret, UC bootstrap privileges and Free-Edition-only objects (M1, M6-M8), GitHub publication. |

**Write set:** everything in `dd-chain-infrastructure`; its state keys; the live dev
resources above; live PRD Ethereum resources (destroy only); capture's
`AWS_CAPTURE_PUBLISH_ROLE` (seed output). **Non-goals:** creating any prd environment
resource; enabling a schedule; VPC/NAT; digest-resolved images; edits in `dd-chain-capture`.

### 2.2 WS-X — `dd-chain-explorer`: bundle `job_market_data`

| # | Goal |
|---|---|
| X1 | **One bundle `apps/dabs/job_market_data/`** (R19): `dev` real (dev SP `run_as`, `[dev] ` prefix, `catalog=dev`), `prod` declared never deployed (R18); **one serverless job `dm-market-data`, three chained PySpark batch tasks `bronze → silver → gold`**, Delta writes only; no `pipelines:` resource, no `dlt` import. |
| X2 | **Parsers reused, not rewritten**: `dm_market_parsers` (pure Python, tested off-cluster) moves with the bundle unchanged. |
| X3 | **Bronze `b_market`** — every partition whose `_manifest.json` sha256 is not yet in `raw_manifests`: one table per dataset (11, §6) of undecoded bytes (`binaryFile`) + `source, dataset, ingest_date, file_name, content_sha256, _ingested_at`, and `raw_manifests` (explicit schema); MERGE on `content_sha256` — a rerun adds nothing (R13). |
| X4 | **Silver `s_market`** — 8 tables (§6, PLAN §4.3), MERGE on each natural key. Former expectations become task checks: parse failure, `content_sha256 ∉` the partition manifest, `versao IS NULL` → rejected and counted, never coerced. `cvm_statements` = DFP + ITR `{BPA,BPP,DRE,DFC_MI}_con`, `vl_conta × ESCALA_MOEDA`, **max `VERSAO` per (cnpj, dt_refer, statement, grupo_dfp), `ORDEM_EXERC = ÚLTIMO`**. FRE/IPE/trade-information bronze-only. |
| X5 | **Gold `g_market`** — 3 tables by overwrite: `company_daily_price` (market cap via `cvm_fca_securities`; NULL never fabricated); `ibov_constituents_daily`; `company_fundamentals_snapshot` (TTM, EBITDA = EBIT + D&A, `pl pvp ev_ebitda roe roic margins dl_ebitda`; `dy` NULL deferred; banks EBITDA NULL; no CAGR). |
| X6 | **File-arrival trigger (R20)** on a new `_manifest.json` under `s3://<raw-bucket>/raw/` (location `dm-dev-raw-data`); `UNPAUSED` in `dev`; `max_concurrent_runs: 1`; no cron, no CI-started run. |
| X7 | **Tests, docs.** Parser suite kept; bundle contract → exactly **1** bundle (1 job, 3 ordered tasks, serverless, file-arrival); no-`dlt`-import contract; seam 3 kept in `docs/cross-repo-contract.md`; README one bundle; versions `0.7.0`. |
| X8 | **Ethereum and DLT code destroyed (R21, O-10).** CI `bundle destroy -t dev` for `dlt_market_data` and the seven Ethereum bundles (`dlt_ethereum`, `dlt_app_logs`, `job_export_gold`, `dashboard_{api_health,gas_analytics,hot_contracts,network_overview}`), taking their SP state dirs; then the sources die: those eight dirs, `apps/lambda/`, the lambda seam's explorer half (`utils/`, `publish-artifacts.yml`; §11), dashboard tooling, their tests. |
| X9 | **Zero-manual chain, explorer half.** The infra signal deploys the bundle to `dev` with no hand filter (M11); the first run is a file-arrival fire, never a hand start (M13). |

**Write set:** everything in the new `dd-chain-explorer`; live Databricks `dev` (this bundle;
destroy of the eight retired); `specs/**` in the authoritative tree (O-9).
**Non-goals:** dashboards; DY; CAGR; FRE/IPE silver; any prod deploy; DLT.

### 2.3 WS-O — operator-only surface

The trust seed run and environment-gate approvals; the constitution amendment
(operator-confirmed). Any other hand act found is an M-step (O-11).

## 3. Scope — OUT

| Out of scope | Reason |
|---|---|
| Creating any PRD environment resource; `schedules_enabled = true` | R4/R18; enabling is an operator ruling |
| Digest-resolved images; managed VPC/NAT | Q3; budget |
| DLT in any form | R19 — batch "for now"; re-entry needs a ruling |
| DY, payout, CAGR, dashboards, Genie; FRE/IPE silver; Basel ratio | R11 source gap; `financial-sources-expansion-data-model` |
| Any Ethereum capability | R21 supersedes R1 |
| `capture-ecr-state-and-kms-ownership-transfer`, `terraform-single-stack-tree-per-env-tfvars`; `dadaia-agents`; edits in `dd-chain-capture` | owned elsewhere; R10; capture context |

## 4. Acceptance criteria

`<raw-bucket>` = `dm-chain-explorer-dev-raw-data`; no account id, host or personal
identifier in any evidence (public repository).

| AC | WS | Verification | Pass condition |
|---|---|---|---|
| AC-1 | I | `pytest -k namespace` at the I1, then the I2 commit | RED naming `scheduler`, then GREEN; bug `resolved` |
| AC-2 | I | plan of `00_bootstrap`; `simulate-principal-policy` on `gha_capture_publish` | 1 role added, documents changed, 0 destroyed; `ecr:PutImage` on a capture repo allowed; other repos, `s3:PutObject`, `ecs:RunTask`, `iam:PassRole` denied |
| AC-3 | I | `gh variable list` in `dd-chain-capture` | `AWS_CAPTURE_PUBLISH_ROLE` set by the script; no `ECR_REGISTRY` |
| AC-4 | I | `ecr describe-repositories`, `get-lifecycle-policy` | three capture repos, MUTABLE, scan on push, both rules |
| AC-5 | I | bucket probes; writer role `simulate-principal-policy` | IT day 0, **no `Expiration`**, four blocks `true`; MFA trust; `PutObject raw/*` allowed, delete and other buckets denied |
| AC-6 | I | CI plan of `dev/03_capture`; `scheduler list-schedules` | 3 task definitions on `<ecr-url>:dev`; SG no ingress; 7 schedules `DISABLED` |
| AC-7 | I | UC plan before/after CI apply; `grants get-effective`; `external-locations validate` | 3 adds, then `No changes`; SP privileges effective; `dm-dev-raw-data` validates |
| AC-8 | I | `pytest scripts/ci/tests` in CI; `grep` workflows; `ls scripts/ci` | green, I8 collected; one `dev-deploy` job; no `detect_changes.sh`; `plan-dev-unity-catalog` has `environment: dev`; map stacks in drift + destroy-all; `actionlint` + `zizmor` clean |
| AC-9 | I | fresh-clone `terraform plan` of every CI stack in `stack_map.json`, OIDC | `0/0/0` each *(amended: was "six stacks")* |
| AC-10 | I | `grep -rn 'own VPS\|Nothing in this repository captures\|HeadObject\|ECR_REGISTRY\|detect_changes'`; `cat VERSION` | 0 hits; `0.7.0` |
| AC-15 | X | read `docs/cross-repo-contract.md`, `apps/dabs/README.md`; versions `sort -u` | seam 3 stated once; lambda seam and every Ethereum row gone *(amended: was "parked")*; `0.7.0` |
| AC-17 | O | `git diff specs/constitution.md` | §1 image seam in, lambda seam out; §2 DynamoDB clause out; §6 UC path; §7 batch raw layout + `Market data` row, Ethereum row and `@dlt` rule out; §10 classification row *(amended)* |
| AC-18 | V | each changed repo's `feature/0.7.0` → `develop` PR; secret scan; trio | all green after v0.6.0's merge; 0 findings; qa, code, security APPROVED per repo |
| AC-19 | X | `ls apps apps/dabs`; `pytest tests` without `pyspark`; `grep -rnE '(import\|from) dlt\|@dlt\.' apps tests` | one bundle `job_market_data`; no `apps/lambda`, no `utils/`; contract: 1 job, `bronze → silver → gold`, serverless, file-arrival; parser fixtures (COTAHIST `preult` ÷100, 244-char line rejected, Latin-1 round-trip, VERSAO max, YTD differencing); grep 0 |
| AC-20 | X | `bundle validate -t dev` and `-t prod` | exit 0 both; prod never deployed |
| AC-21 | X | `bundle summary -t dev`; `jobs get`; `pipelines list`; SP `.bundle/` | one job `[dev] dm-market-data`, 3 tasks, serverless, `file_arrival` trigger on the landing `UNPAUSED`; 0 pipelines; no Ethereum job/dashboard; `.bundle/` holds this bundle only |
| AC-22 | X | **the POC gate** — CLOSURE table, one `ingest_date` per image landed by a workflow-run Fargate task | raw keys + manifest sha256; the run's trigger is file arrival; `SHOW TABLES` 12 / 8 / 3; rows per layer, every `g_market` table > 0; 0 sha rejections; a second fire over the same partition changes no count |
| AC-23 | E | `schemas list dev`; `external-locations get dm-dev-ingestion`; `head-bucket`; `dynamodb list-tables`; `lambda list-functions`/`list-layers`; `scheduler get-schedule`; `ecr describe-repositories`; `iam get-role …artifacts-publish`; `stack_map.json`; `grep -rniE 'ethereum\|etherscan\|dynamodb'` explorer `apps tests .github`, infra `services scripts .github` | all R21 objects and the lambda seam absent; ECR holds the 3 capture repos only; no `lambda` stack; each removal cites a CI run id, none a laptop CLI; grep 0 |
| AC-24 | C | CLOSURE M-ledger table; the chain's run list; seed run twice | every M-step → workflow + job, seed step, or retired one-off with reason, none `manual`; one chain from a `develop` merge yields AC-22 with every run event ∈ push / workflow_run / repository_dispatch / file arrival and human acts only environment approvals; second seed run = no changes, no secret echoed; drift on the deploy branch = 0 |

**Superseded (not evidence):** AC-11 (8 bundles + DLT expectations) → AC-19 · AC-12 → AC-20
· AC-13 (pipeline + PAUSED job) → AC-21 · AC-14 (first DLT update) → AC-22 · AC-16 (hand
smoke + hand `run-task`, = M14) → AC-22/AC-24.
**Ship gate:** AC-1..10, AC-15, AC-17..24 green; memory (§9); CLOSURE; promote-or-continue is
the operator's.

## 5. Ordering safety

| # | Rule |
|---|---|
| O-1 | **v0.6.0 first (R5).** `feature/0.7.0` stacks on `feature/0.6.0` and merges into `develop` after v0.6.0's merge. |
| O-2 | **Bug before fix.** Bug record and RED test land before any grant. |
| O-3 | **Bootstrap → registry → images → runtime**; schedules stay `DISABLED`. |
| O-4 | **Bucket before external location.** |
| O-5 | **The UC stack creates only I6's three objects**; a non-importable object escalates (ADR-5). |
| O-6 | **Real bytes before the first run** — partitions landed by the images, never fixtures in the real bucket. |
| O-7 | **No PRD creation; PRD destruction only through the prd lane gate.** `prod` targets declared, never deployed (R18). |
| O-8 | **Secrets are never copied.** Typed once into the seed or published by it; agents reference names. |
| O-9 | **Specs write where authority is** — the legacy tree until v0.6.0's C-DAY, the new explorer after. |
| O-10 | **Destroy before delete.** Every deployed object is destroyed by CI while its source exists; the source dies in a later commit; nothing is removed from a laptop (M9 not repeated). The DLT pipeline is destroyed before the job's first run, so no DLT-owned table shadows a job-written one. |
| O-11 | **Seed once, workflows for the rest.** An act no workflow reproduces is a seed step or an open M-step, appended the day it happens. |

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
**capture runtime** — cluster, task definitions, schedules running the images; **image seam**
— the ECR registry fed by capture CI (seam 3); **file-arrival trigger** — the Databricks job
trigger firing on new files under a UC external-location path; **trust seed** — the one
scripted, idempotent operator act per account (I11); **M-step** — one hand act in the
`cicd-zero-manual-steps` ledger; **retirement job** — the idempotent CI job removing objects
no Terraform or bundle state owns.

## 7. Bugs and backlog

- **Consumed:** `market-data-medallion-restart`, `batch-medallion-and-ethereum-retirement`,
  `cicd-zero-manual-steps`, `e2e-dev-validation-financial-lakehouse` — `picked (v0.7.0)`;
  LEDGER lines at CLOSURE.
- **Exit at CLOSURE `REJECTED · obsolete-by-R21`:** `dlt-ethereum-data-quality-enhancements`,
  `dashboards-analytics-enrichment`, `s3-raw-lifecycle-intelligent-tiering`,
  `rest-api-public-endpoint`, `encryption-at-rest-posture-decision`.
- **Picked bug:** `deploy-roles-lack-scheduler-grants-for-declared-schedule` — T-I7.1/T-I7.2.

## 8. Execution model

Legacy tree until C-DAY (O-9); `feature/0.7.0` in both repos. **(a)** trio `Aprovado` ·
**(b)** runtime T-I7.1..8 → AC-1..10 · **(c)** batch rework, DLT pipeline destroyed →
AC-19..21 · **(d)** Ethereum teardown, destroy then delete → AC-23 · **(e)** chain + trust
seed → AC-22, AC-24 · **ship:** trio APPROVED per repo (AC-18); memory → CLOSURE → merges;
promote-or-continue. The DLT slices T-X7.1..5 are superseded in `TASKS.md`, not re-litigated.

## 9. Memory files affected at CLOSURE (do NOT write now)

- `memory/architecture.md` — ADR-007 rescoped (batch capture runtime hosted here); new ADRs: image seam + CI-applied UC stack; batch Jobs not DLT (R19); Ethereum lane + lambda seam retired (R21); ADR-003 DynamoDB deleted; data flow redrawn.
- `memory/tech-stack.md` — ECS Fargate/Spot, ECR, Scheduler in; Lambda, DynamoDB, DLT out; one serverless job, file-arrival trigger.
- `product/capture-layer.md` — three images, seven jobs, raw contract, writer role; Ethereum lane retired.
- `product/medallion-pipelines.md`, `product/data-catalog.md` — `job_market_data`, 12/8/3, MERGE/overwrite; Ethereum objects deleted.
- `product/serving-layer.md` — dashboards, export job, Lambda path deleted; serving = SQL over `g_market`.
- `product/aws-resources.md`, `product/cicd-pipeline.md` — raw bucket, ECR, capture + UC stacks; ingestion, DynamoDB, Lambdas, artifacts seam gone; chained lanes, trust seed, drift on the deploy branch.
- `memory/quality-assurance.md` — parser suite, namespace-coverage family, 1-bundle + no-`dlt` contracts.
- `product/index.md`, `catalog.json` — membership as changed; `constitution.md` — T-O7.5 per AC-17.

## 10. Dependencies & risks

| Risk / dependency | Mitigation |
|---|---|
| **Databricks org status refused job creation and pipeline updates (09-21)** — the batch job inherits it | operator account act, an M-step until covered; AC-21/22 block on it, nothing faked |
| **File-arrival triggers cap the watched file count without file events**; the landing never expires (R14) | PLAN picks file events on `dm-dev-raw-data` or a bounded path; AC-21 proves it live |
| **Cross-repo events need a credential** | minted by the seed (GitHub App / fine-grained token), never a copied PAT (O-8) |
| **Bootstrap re-apply is operator + MFA**; **C-DAY moves the authoritative tree** | folded into the seed; O-9 |
| **Mutable `:dev`; Spot interruption; default VPC absent** | schedules `DISABLED`; digest in the manifest; manifest-last + idempotent MERGE |
| **Layout/encoding drift; bank/D&A account codes; ON/PN market cap** | parsers reject, never coerce; fixtures pin layouts; ratios NULL without inputs; D&A on ≥ 3 fixture companies |

## 11. Decisions resolved

**R1-R17** (grill 2026-09-12/13, full text in the handoff), load-bearing: ~~R1 Ethereum
parked~~ (superseded by R21) · **R4** dev first, PRD-compatible, no PRD resources · **R5**
v0.6.0 first · **R9** SP grants in the UC stack · **R11** three images / seven jobs · **R12**
ECR + narrow `gha_capture_publish` · **R13** raw = untouched bytes + manifest · **R14** raw
bucket, no expiry, IT · **R15** B3 daily 00:30 UTC, CVM weekly, BCB daily, floor 2010.

**R18-R22 (operator, 2026-09-23).** **R18** Free Edition = DEV only (ADR-10 reaffirmed) ·
**R19** no DLT: one bundle, one serverless job, three chained PySpark batch tasks, Delta by
MERGE/overwrite, tested parsers reused · **R20** file-arrival trigger over the raw landing ·
**R21** the Ethereum lane destroyed everywhere through IaC/CI (schemas + bundle state, 7
bundles, ingestion bucket + location, DynamoDB, both Lambdas, ECR stream/connect, the PRD
schedule) · **R22** all inside v0.7.0; the DEV e2e is proven on the batch shape and
`cicd-zero-manual-steps` is a closure gate beside it.

**PM rulings 2026-09-13.** Q1 ECR in `prd/04_peripherals` · Q2 UC stack under the CI dev lane
· Q3 mutable `:dev` + digest in the manifest · Q4 CVM weekly · Q5 constitution = OPERATOR-ONLY.
**SPEC additions 2026-09-13.** Singular `databricks_grant`; bronze `binaryFile`, manifest join
at silver; FRE/IPE bronze-only; market-cap class rule; NULL-never-fabricate; writer-role MFA.

**SPEC additions 2026-09-23 — the operator may object before the tasks start.** Bundle name
`job_market_data` (the `job_*` convention). Expectations become counted task rejections
(X4). The **lambda seam dies with the Lambdas** (I10, X8): `utils/` (`dm_chain_utils`:
etherscan, DynamoDB, parameter store), `publish-artifacts.yml`, `s3_artifacts`,
`gha_artifacts_publish` serve only the two Lambdas R21 destroys (deletion test). Stateless
objects go through one retirement job. The DLT pipeline dies before the job's first run.
