# SPEC — Release v0.7.0 — Market-data restart: batch capture runtime + medallion landing

> **Status:** Aprovado
> **Release ID:** v0.7.0
> **Owner:** product-engineer — approved under the operator standing order of 2026-09-13 ("faça tudo que puder, avance"), after the operator ratified grill rulings R1-R17 (2026-09-12/13)
> **Created / Approved:** 2026-09-13
> **Lifecycle:** **v0.6.0 stays the live release until its C-DAY; v0.7.0 is authored now, pre-staged, and becomes ACTIVE only when v0.6.0 closes.** `releases/ACTIVE.md` is untouched; the trio travels inside `releases/**` at v0.6.0's `T-V.4` handover.
> **Consumes:** market-data-medallion-restart
> **Provenance:** grill handoff `2026-09-13T011657Z-project-manager-restart-audit-grill` (R1-R17) · backlog entry `market-data-medallion-restart` · architect DRAFT `dd-chain-infrastructure/docs/design/batch-capture-runtime.md` (§9 defaults ruled by the PM) · capture v0.5.0 `SPEC`/`CLOSURE`, atoms `batch-capture-lane`, `raw-landing-contract` · source study Part C
> **Scope (operator-locked):** dev only (R4). WS-I — the infrastructure that runs the three capture images and lands their raw bytes; WS-X — the first medallion bundle reading that landing into bronze/silver/gold company metrics. No PRD environment resource; the Ethereum lane stays parked and undeployed (R1). Statement-, column- and test-level detail: `PLAN.md` §3-§4.

## 1. Problem

`dd-chain-capture` v0.5.0 shipped three images (`b3-market-data`, `cvm-open-data`,
`bcb-sgs`), seven jobs and the raw contract (untouched bytes under
`raw/<source>/<dataset>/ingest_date=YYYY-MM-DD/` + `_manifest.json` `raw-manifest-v1`
written last), but nothing exists to run them or receive their bytes: no bucket, no ECR
repository, no `gha_capture_publish` role, no Fargate runtime. Downstream, no bundle reads
the new layout.

Two structural facts bind the infrastructure half. **(a)** The deploy and read-only roles
grant no `scheduler:` action although `prd/06_lambda` declares a schedule — a latent HIGH of
the same family as the four ledger bugs on this surface (hand-maintained policy, no test
tying it to `services/**`); fixed structurally, namespace-coverage test RED first. **(b)** The
UC stack `services/databricks` sits outside CI, so R9 cannot land through CI and ADR-6
forbids an operator apply: it becomes dev infrastructure under the CI dev lane.

## 2. Scope — IN

Write sets are disjoint by repository: WS-I → `dd-chain-infrastructure`, WS-X → the new
`dd-chain-explorer`, WS-O → operator acts only. Both repos work on `feature/0.7.0`, stacked
on `feature/0.6.0` (O-1).

### 2.1 WS-I — `dd-chain-infrastructure`: the batch capture runtime

| # | Goal |
|---|---|
| I1 | **Bug first, then the structural fix.** Register `deploy-roles-lack-scheduler-grants-for-declared-schedule` (`caused_by: none`); add `test_every_aws_service_namespace_declared_in_services_is_granted` (every `aws_<svc>_*` resource under `services/{dev,prd}` has a deploy Allow and a read-only read Allow; every assume-role `Principal.Service` is in `ProjectIamPassRole`). RED on `scheduler`, GREEN after I2. No one-line `scheduler:*` patch. |
| I2 | **Bootstrap delta** (`prd/00_bootstrap`, operator-applied): role `gha_capture_publish` (OIDC trust to `dd-chain-capture` envs `dev`/`production`, boundary, self-mutation deny, ECR push/pull on the three capture repos); deploy/read-only/boundary statements per PLAN §3.2 (one conditioned `iam:PassRole`; `"*"` only for `RESOURCELESS_ACTIONS`); debug user may assume the writer role; `s3:HeadObject` deleted; `publish_oidc_vars.sh --target infra\|explorer\|capture`. |
| I3 | **ECR ×3 + lifecycle** in `prd/04_peripherals`: `dm-chain-explorer-capture/<image>`, MUTABLE, scan on push, `force_delete`, lifecycle (untagged > 1 d; > 10 images); applied via the prd lane's informed gate. `empty_s3_and_ecr.sh` → `empty_s3_buckets.sh`. |
| I4 | **Dev raw landing** in `dev/01_peripherals`: bucket `dm-chain-explorer-dev-raw-data` (PAB, SSE-S3, `INTELLIGENT_TIERING` at day 0, **no expiration**); MFA-gated writer role `dm-chain-explorer-capture-dev-writer` (put/get/abort + prefix-scoped list on `raw/*`, no delete, boundary); `databricks_dev_s3_policy` widened — one credential per environment. |
| I5 | **New stack `dev/03_capture`**: Fargate/Spot cluster, log group, egress-only SG in the **default VPC** (public IP, no NAT), exec role, one task role per image scoped to `raw/<source>/*`, three task definitions (`<ecr-url>:${var.image_tag}`, default `dev`, no command), scheduler role, **seven schedules `DISABLED` by default** (R15 cadence, `input.command = [<job>]`); runbook `docs/runbooks/capture-backfill.md` (`aws ecs run-task` is data-plane, not an ADR-6 mutation). |
| I6 | **UC stack relocated and completed**: `git mv services/databricks services/dev/04_unity_catalog` (state key unchanged); external location `dm-dev-raw-data`; two **singular** `databricks_grant` for `var.databricks_dev_sp_application_id` (catalog privileges + `READ_FILES`); plural `databricks_grants` rejected (would revoke operator grants); exactly three creates. Supersedes v0.6.0 T-X.8(a). |
| I7 | **CI map-driven, replace-don't-layer**: `stack_map.json` gains `dev.capture` and `dev.unity_catalog`; `deploy_env.sh dev` iterates the map and one `dev-deploy` job replaces `dev-detect-changes` + two static jobs; **`detect_changes.sh` is deleted**; `plan_on_pr.yml` (+2, `plan-dev-unity-catalog` bound to `environment: dev`), `drift_detection.yml` (+2), `destroy_all_cloud_infra.yml` (+2). |
| I8 | **Contract tests** (PLAN §3.4): the I1 namespace test; publish-role minimality; `capture_images` equality bootstrap ↔ `prd/04`; schedules default `DISABLED`; task-role policies prefix-scoped; schedule ↔ container name; dev-lane apply order; every existing pin re-anchored. |
| I9 | **Words and version.** `AGENTS.md`/`README.md`: capture *code and images* live in `dd-chain-capture`; this repository hosts the runtime that runs them. `vars.ECR_REGISTRY` never exists. Root `VERSION` = `0.7.0`. |

**Write set:** everything inside `dd-chain-infrastructure`; state keys `prd/bootstrap`
(operator), `prd/peripherals`, `dev/peripherals`, `dev/capture/terraform.tfstate`,
`databricks/unity-catalog/terraform.tfstate`; the live dev resources above; variable
`AWS_CAPTURE_PUBLISH_ROLE` in `dd-chain-capture` (operator-run script).
**Non-goals:** any prd *environment* resource (the account-scoped registry is not one, Q1);
enabling a schedule; managed VPC/NAT; digest-resolved images; `dm-chain-explorer-dev-ingestion`.

### 2.2 WS-X — `dd-chain-explorer`: bundle `dlt_market_data`

| # | Goal |
|---|---|
| X1 | **One new bundle** `apps/dabs/dlt_market_data/` on the `dlt_ethereum` pattern: `dev` real (dev SP `run_as`, `[dev] ` prefix, `catalog=dev`, raw bucket var), `prod` declared never deployed; pipeline `dm-market-data` serverless, triggered, publishing to `b_market`/`s_market`/`g_market`; trigger job **PAUSED**; `VERSION` `0.7.0`; no dashboard; Ethereum bundles unchanged, undeployed. |
| X2 | **Pure-Python parsers** under the bundle's `src/`, importable without `pyspark`: COTAHIST fixed-width, `;`-Latin-1 CSV (CVM members, B3 consolidated files), ZIP members, indexProxy JSON, SGS JSON, VERSAO dedupe, ITR YTD differencing (interfaces: PLAN §4.2). Deletion test: without them, 11 bronze→silver paths re-implement Latin-1 + layout logic inside DLT closures, untestable off-cluster. |
| X3 | **Bronze `b_market`** — one Auto Loader `binaryFile` streaming table per dataset (11, §6) plus `raw_manifests` (Auto Loader `json`, explicit `raw-manifest-v1` schema); derived `source, dataset, ingest_date, file_name, content_sha256, _ingested_at`. Bytes are never decoded in bronze — `text` would UTF-8-decode Latin-1 (R13). |
| X4 | **Silver `s_market`** — 8 streaming tables (§6; columns PLAN §4.3); every expectation lives here: parse success (`expect_or_drop`), `content_sha256 ∈ raw_manifests.files[].sha256` of the partition, `versao IS NOT NULL`. `cvm_statements` = DFP + ITR union of `{BPA,BPP,DRE,DFC_MI}_con`, `vl_conta × ESCALA_MOEDA`, **max `VERSAO` per (cnpj, dt_refer, statement, grupo_dfp), `ORDEM_EXERC = ÚLTIMO` only**. FRE/IPE and the trade-information file stay bronze-only (IPE is a PDF index; FRE `posicao_acionaria` may name natural persons — §10 review). |
| X5 | **Gold `g_market` first cut** — 3 MVs: `company_daily_price` (close, volume, shares, market cap via `cvm_fca_securities`; NULL never fabricated); `ibov_constituents_daily`; `company_fundamentals_snapshot` per (cnpj, dt_refer): TTM lines (codes PLAN §4.3), EBITDA = EBIT + D&A, ratios `pl, pvp, ev_ebitda, roe, roic, margins, dl_ebitda`, `dy` NULL (`dy_status = deferred`); banks: EBITDA fields NULL; no CAGR. |
| X6 | **Tests, entrypoints, docs.** Parser tests with small public fixtures; bundle-count contract → **8**; expectations contract covers the pipeline; Makefile `dabs_run_dlt_market_data`; `docs/cross-repo-contract.md` gains **seam 3 — the image seam** (registry `dm-chain-explorer-capture/<image>`, tag rules, single variable `AWS_CAPTURE_PUBLISH_ROLE`, digest in `_manifest.json`, UC stack path); `apps/dabs/README.md` 8 bundles, Ethereum parked; versions `0.7.0`. |
| X7 | **Dev deploy and first update** after real partitions exist (T-O7.4): `bundle deploy -t dev` for **this bundle only** (`dabs_deploy_all` is not run); one manual update; bronze and silver rows for at least `bcb/sgs`; trigger job still PAUSED. |

**Write set:** everything inside the new `dd-chain-explorer`; the live Databricks `dev`
target (this bundle's resources only); `specs/**` in the authoritative tree (O-9).
**Non-goals:** dashboards; dividends/DY; CAGR; FRE/IPE silver; any prod deploy; any
Ethereum bundle; `job_export_gold`/Lambda changes.

### 2.3 WS-O — operator-only surface

Bootstrap apply + OIDC variable publish; the infra repo's `dev` GitHub environment
(Databricks secrets, `TF_VAR_databricks_dev_sp_application_id`); the first dev-lane apply of
the UC stack; the first real landing (smoke via the MFA writer role, one `aws ecs run-task`);
the constitution amendment. Each is an `OPERATOR-ONLY` row in `TASKS.md`.

## 3. Scope — OUT

| Out of scope | Reason |
|---|---|
| Any PRD environment resource; v0.6.0 `T-I.17`, `T-X.8(b,c)`, `T-X.2(prod)`; `schedules_enabled = true` | R4; enabling = one variable edit after the first Fargate proof, ruled by the operator |
| Digest-resolved images; managed VPC/NAT/endpoints | Q3; budget — default VPC + egress SG, fallback documented, not built |
| Dividends, DY, payout, CAGR, dashboards, Genie; FRE/IPE silver, `posicao_acionaria`, Basel ratio | source gap (brapi ToS unread, R11) / need populated gold; next candidate after the §10 classification review |
| Ethereum bundles and the five parked entries (`dlt-ethereum-data-quality-enhancements`, `dashboards-analytics-enrichment`, `s3-raw-lifecycle-intelligent-tiering`, `rest-api-public-endpoint`, `encryption-at-rest-posture-decision`) | R1 — ACTIVE, unpickable while parked |
| `capture-ecr-state-and-kms-ownership-transfer`, `terraform-single-stack-tree-per-env-tfvars`; the consumer agent / `dadaia-agents`; constitution §2 `hml` row | owned elsewhere / restructuring; R10; v0.6.0 ADR-10 residual flagged to the PM |

## 4. Acceptance criteria

`<raw-bucket>` = `dm-chain-explorer-dev-raw-data`; no account id, host or personal
identifier in any evidence (public repository).

| AC | WS | Verification | Pass condition |
|---|---|---|---|
| AC-1 | I | `pytest -k namespace` at the I1 commit, then at the I2 commit | RED naming `scheduler`, then GREEN — both recorded; bug `open` → `resolved`, `caused_by: none` |
| AC-2 | I | operator plan of `00_bootstrap`; `simulate-principal-policy` on `gha_capture_publish` | 1 role added, documents changed, 0 destroyed; `ecr:PutImage` on a capture repo `allowed`; on any other repo, `s3:PutObject` on `<raw-bucket>`, `ecs:RunTask`, `iam:PassRole` denied |
| AC-3 | I | `gh variable list` in `dd-chain-capture` (names only) | `AWS_CAPTURE_PUBLISH_ROLE` non-empty, set by the script; no `ECR_REGISTRY` |
| AC-4 | I | `aws ecr describe-repositories`, `get-lifecycle-policy` | three `dm-chain-explorer-capture/<image>`, MUTABLE, scan on push, both rules |
| AC-5 | I | bucket probes (`head-bucket`, lifecycle, public-access-block); writer-role `get-role` + `simulate-principal-policy` | 200; one rule `INTELLIGENT_TIERING` day 0, **no `Expiration`**; four blocks `true`; trust requires MFA; `PutObject raw/*` allowed, `DeleteObject` and other buckets denied |
| AC-6 | I | CI plan of `dev/03_capture` once images exist; `aws scheduler list-schedules` | 3 task definitions resolving `<ecr-url>:dev`; SG with no ingress; 7 schedules `DISABLED` |
| AC-7 | I | plan of `dev/04_unity_catalog` before/after its CI apply; `grants get-effective`; `external-locations validate` | before: exactly 3 to add; after: `No changes`; seven privileges effective for the dev SP; `dm-dev-raw-data` validates |
| AC-8 | I | `pytest scripts/ci/tests -p no:cacheprovider` in CI; `grep` the six workflows; `ls scripts/ci` | green, I8 tests collected; one `dev-deploy` job; no `detect_changes.sh`; `plan-dev-unity-catalog` has `environment: dev`; both new stacks in drift and destroy-all; `actionlint` + `zizmor` clean |
| AC-9 | I | fresh-clone `terraform plan`, every non-operator stack, under OIDC | `0/0/0` on all six stacks after this release's applies |
| AC-10 | I | `grep -rn 'own VPS\|Nothing in this repository captures\|HeadObject\|ECR_REGISTRY\|detect_changes' AGENTS.md README.md services scripts .github`; `cat VERSION` | 0 hits; `0.7.0` |
| AC-11 | X | `ls apps/dabs`; `pytest tests -p no:cacheprovider` without `pyspark` | 8 bundles; targets and expectations contracts pass; parser fixtures: COTAHIST `preult` ÷100 and a 244-char line rejected, Latin-1 `ç`/`ã` round-trip, VERSAO dedupe keeps the max, YTD differencing yields the quarter |
| AC-12 | X | `make dabs_validate_all TARGET=dev`; `bundle validate -t prod` on `main` | exit 0 for all 8; prod validates with the production host (validate only) |
| AC-13 | X | `bundle summary -t dev`; `pipelines get`; workspace listing | one pipeline `[dev] dm-market-data`, serverless, `continuous=false`; trigger job `PAUSED`; **no** Ethereum pipeline/job/dashboard deployed |
| AC-14 | X | `SHOW TABLES IN dev.{b_market,s_market,g_market}` after the first update | 12 / 8 / 3 objects; `b_market.bcb_sgs` and `s_market.bcb_series` carry the T-O7.4 rows; 0 drops on the sha expectation |
| AC-15 | X | read `docs/cross-repo-contract.md`, `apps/dabs/README.md`; `cat VERSION apps/dabs/*/VERSION \| sort -u` | seam 3 stated once (registry, tags, one variable, digest, six roles); Ethereum row parked; `0.7.0` |
| AC-16 | O | evidence lines in CLOSURE | `publish-images.yml` green (3 images `:dev`); `make batch-smoke-real` landed `raw/bcb/sgs/ingest_date=<d>/` with a valid manifest; one `aws ecs run-task` of `bcb-sgs` landed a partition from Fargate |
| AC-17 | O | `git diff specs/constitution.md`; `dadaia specs doctor` | §1 third seam; §6 UC stack path; §7 batch raw layout + `Market data` medallion row; §10 classification row with the `posicao_acionaria` reservation; 0 errors |
| AC-18 | V | both repos' `feature/0.7.0` → `develop` PR checks; secret scan; trio handoffs | all checks green in both (after v0.6.0's merge); zero scan findings; `qa-engineer`, `code-reviewer`, `security-reviewer` APPROVED per repo |

**Ship gate:** AC-1..AC-18 green; memory (§9) updated; CLOSURE recorded; promote-or-continue
is the operator's.

## 5. Ordering safety

| # | Rule |
|---|---|
| O-1 | **v0.6.0 first (R5).** `feature/0.7.0` is cut from `feature/0.6.0` in both repos and merges into `develop` only after v0.6.0's candidate merge; v0.6.0 `T-X.8(a)` is superseded by I6, nothing else is re-litigated. |
| O-2 | **Bug before fix.** The bug record and the RED namespace test land in their own commits before any grant is added. |
| O-3 | **Bootstrap → registry → images → runtime.** Verdict → operator bootstrap apply + variable publish → prd lane applies ECR → capture `publish-images.yml` pushes `:dev` → `dev/03_capture` plans with resolvable image URLs → local proof; schedules stay `DISABLED`. |
| O-4 | **Bucket before external location.** `dev/01_peripherals` applies before `dev/04_unity_catalog` creates the location, whose creation validates the credential against the bucket. |
| O-5 | **Relocate only an imported stack.** The `git mv` follows v0.6.0 `T-I.12`'s post-import `No changes`; the stack's only creates ever are I6's three adds; a non-importable object still escalates (ADR-5). |
| O-6 | **Real bytes before the first update.** Bronze is first exercised against partitions landed by the capture images (T-O7.4), never against fixtures uploaded to the real bucket. |
| O-7 | **No PRD environment resource; Ethereum untouched.** The registry is account-scoped shared infrastructure (Q1); `prod` bundle targets are declared, never deployed; no Ethereum bundle file changes; `dabs_deploy_all` is not run. |
| O-8 | **Secrets are never copied.** Databricks values and role ARNs are typed by the operator or published by the operator-run script; agents reference names only. |
| O-9 | **Specs write where authority is.** Before v0.6.0's C-DAY this trio lives in the legacy tree, written only by PM-authorized marker flips; after C-DAY every write happens in the new `dd-chain-explorer`. I1's bug is registered in the authoritative ledger of the moment. |

## 6. The dataset contract — raw → bronze → silver → gold

Raw partition `raw/<source>/<dataset>/ingest_date=YYYY-MM-DD/`; B = bronze table, S =
silver table, G = gold consumer (`company_daily_price`, `ibov_constituents_daily`,
`company_fundamentals_snapshot`, X5).

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

**Glossary.** *source*, *dataset*, *partition*, *manifest* — as in `dd-chain-capture`'s
`raw-landing-contract`; **capture runtime** — the Fargate cluster, task definitions and
schedules that run the images (hosted here; the images are not); **image seam** — the ECR
registry fed by capture CI and pulled by the runtime (seam 3).

## 7. Bugs and backlog

- **Consumed:** `market-data-medallion-restart` — `Status: picked (v0.7.0, pre-staged)` in
  this commit; histo line at CLOSURE's disposition sweep.
- **Picked bug:** `deploy-roles-lack-scheduler-grants-for-declared-schedule` (HIGH, latent)
  — registered by T-I7.1, fixed in-candidate by T-I7.2; regression seam = the namespace test.
  No other open record touches this surface.

## 8. Execution model

Definition in the legacy tree while v0.6.0 is live (O-9); implementation on `feature/0.7.0`
in both repos. **(a)** trio `Aprovado` — this commit, pre-staged · **(b)** runtime live:
T-I7.1..8, T-O7.1..3 → AC-1..10 · **(c)** first landing: T-O7.4 → AC-16 · **(d)** first
medallion update: T-X7.1..6 → AC-11..15 · **alpha-1 / rc-1 / ship:** qa review; trio
APPROVED in both repos (AC-18); memory → CLOSURE → `feature → develop` merge in both repos;
then promote-or-continue.

## 9. Memory files affected at CLOSURE (do NOT write now)

- `memory/architecture.md` — ADR-007 **rescoped** (forbidden = the streaming producer fleet; the batch capture *runtime* is hosted here by design); new ADR for the image seam and the CI-applied UC stack; layer table + data flow redrawn.
- `memory/tech-stack.md` — AWS surface gains ECS Fargate/Spot, ECR, Scheduler, default-VPC SG; "no VPC and no container compute" deleted; Databricks gains `dm-market-data`.
- `product/capture-layer.md` — rewritten per the backlog intent: three images, seven jobs, raw contract, writer role; Ethereum streaming lane parked.
- `product/medallion-pipelines.md`, `product/data-catalog.md` — `dlt_market_data`, `b_market`/`s_market`/`g_market` (12/8/3); Ethereum objects deleted from the workspace (R1), code retained.
- `product/aws-resources.md` — `<raw-bucket>`, writer role, ECR ×3, two new stacks + keys, six OIDC roles.
- `product/cicd-pipeline.md` — map-driven dev lane, two new plan/drift jobs, `publish_oidc_vars.sh --target`.
- `memory/quality-assurance.md` — parser suite, namespace-coverage test family, 8-bundle contract.
- `product/serving-layer.md` — no change (reason recorded); `product/index.md`, `catalog.json` — only if membership/rank changes.
- `constitution.md` — T-O7.5, operator-confirmed: §1 third seam; §6 UC stack path; §7 batch raw layout + `Market data` medallion row; §10 classification row.

## 10. Dependencies & risks

| Risk / dependency | Mitigation |
|---|---|
| **GitHub account billing lock** (grill CRITICAL); **bootstrap re-apply is operator + MFA** | no CI evidence claimed until cleared, local gates run meanwhile; O-3, verdict first (T-I7.3), rollback = one apply |
| **v0.6.0 C-DAY moves the authoritative tree**; **the namespace test may surface more than `scheduler`** | O-9, no dual write; each gap closes in T-I7.2 with its own statement, none is silenced |
| **Mutable `:dev`; Spot interruption → partial partition; default VPC absent; DLT multi-schema on Free Edition** | schedules `DISABLED`; digest in the manifest; manifest-last + idempotent reruns (capture contract); plan fails loudly, fallback documented not built; mechanism `dm-ethereum` already used, proven at X1 |
| **Layout/encoding drift; per-company account codes (banks, D&A); ON/PN market cap** | parsers reject into expectation drops, never coerce; fixtures pin layouts; ratios NULL where inputs are absent; D&A mapping validated on ≥ 3 fixture companies; class rule stated in X5 |

## 11. Decisions resolved

**Operator rulings R1-R17** (grill 2026-09-12/13, ratified 2026-09-13; full text in the
handoff) bind this release; load-bearing here: **R1** Ethereum parked, code stays, nothing
deployed · **R4** dev first, PRD compatibility mandatory, PRD resources not · **R5** v0.6.0
first · **R9** SP grants in the UC Terraform stack, hand grants are puxadinho · **R11**
three images / seven jobs, brapi held · **R12** ECR + one narrow `gha_capture_publish` role
· **R13** raw = untouched bytes + manifest, parsing is bronze work · **R14**
`dm-chain-explorer-dev-raw-data`, no expiry, Intelligent-Tiering · **R15** B3 daily 00:30
UTC, CVM weekly Sunday, BCB daily, backfill floor 2010.

**PM rulings on the design's open questions, 2026-09-13.** Q1 ECR home = `prd/04_peripherals`
· Q2 UC stack → `services/dev/04_unity_catalog` under the CI dev lane, Databricks dev
credentials in the infra repo's `dev` environment · Q3 mutable `:dev` tag + digest in the
manifest · Q4 CVM jobs weekly · Q5 constitution amendment = OPERATOR-ONLY task.

**SPEC additions.** Singular `databricks_grant` (I6). Bronze `binaryFile` for every dataset,
manifest join at silver (X3/X4). FRE/IPE and the trade-information file bronze-only (X4).
Market-cap class rule; NULL-never-fabricate (X5). Schedules `DISABLED` for the whole
candidate. The writer role's MFA trust (the grill's "assumption not asked") is adopted as
stated; the operator may object at rc-1.
