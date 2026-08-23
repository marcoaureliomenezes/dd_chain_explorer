# SDD Drift Lane — dd-chain-explorer

**Auditor:** project-auditor (lane: SDD drift — specs, releases, memory, backlog, bugs, prior audits)
**Date:** 2026-08-23
**Context:** dd-chain-explorer · workspace root `<workspace>`
**Repo:** `<repo>`
**Branch audited:** `feature/v0.4.0` @ `c6feb17` (local, ahead-1 of `origin/feature/v0.4.0`)
**Mode:** READ-ONLY. No file under the repo was modified.
**Sub-agents:** none dispatched (nested dispatch unavailable this run). Evidence gathered
directly by this session; live-AWS / Databricks / security / CI-runtime claims are
explicitly deferred to the parallel lanes and are never asserted here as verified.

---

## 0. Executive summary

v0.4.0 "Capture Retirement" is **implementation-complete and release-incomplete**. All
16 TASKS markers are `[x]` and — spot-checked across four workstreams — the claimed
deliverables genuinely exist on disk. But the release never entered CLOSURE: no
`CLOSURE.md`, no memory update, `ACTIVE.md` still says `phase: IMPLEMENTATION`, and the
branch is unmerged and locally ahead-1.

The consequence is the dominant finding of this lane: **every memory atom that describes
the platform's data path still describes the pre-v0.4.0 world.** `architecture.md`,
`tech-stack.md`, `product/aws-resources.md`, `product/capture-layer.md`, `product/index.md`
and `catalog.json` collectively assert 5 live ECS Fargate capture jobs, 3 Kinesis streams,
8 Firehose delivery streams, 12 SQS queues/DLQs and two Terraform modules (`kinesis`, `sqs`)
— all of which were destroyed in AWS on 2026-06-22 and deleted from the repo in the same
change set. An agent that self-pulls memory today is grounded in a system that has not
existed for two months.

Two residues escaped the release's own acceptance criteria because they lay outside every
declared write set: `.github/workflows/deploy_all_dm_applications.yml` still provisions and
tears down HML capture infrastructure (including `terraform destroy -target='module.kinesis'`
against a module that no longer exists), and `services/{prd,hml}/03_iam` still grant/create
Kinesis-Firehose-SQS permissions for destroyed resources. The "streams come back" regression
vector that SPEC §3.2 was written to eliminate survives in the application-deploy lane.

Governance state: `dadaia specs doctor` is **0 errors / 20 warnings**; the backlog is 7 loose
files with no `BACKLOG.md`; `specs/constitution.md` is a 33-byte stub carrying no product law;
the 2026-06-11 full-platform audit (5 CRITICAL / 17 HIGH / 28 MEDIUM / 20 LOW) has **no
per-finding disposition anywhere**; and the single open bug is a dadaia-workspace tooling bug
misfiled in this repo's ledger.

**SDD-lane consolidated score: 3.7 / 10** — significant drift. Per `dd-audit-project`
recommendation policy (`final < 5`), this lane recommends a dedicated remediation release,
opened by `project-manager` on operator decision. This auditor recommends only; it opens
nothing.

---

## 1. Release state — v0.4.0

### 1.1 Status tokens

| Artifact | Status token | Canonical? |
|---|---|---|
| `specs/releases/v0.4.0/SPEC.md:3` | `> **Status:** Aprovado` | yes |
| `specs/releases/v0.4.0/PLAN.md:3` | `> **Status:** Aprovado` | yes |
| `specs/releases/v0.4.0/TASKS.md:3` | `> **Status:** Aprovado` | yes |
| `specs/releases/v0.4.0/CLOSURE.md` | **absent** | — |
| `specs/releases/ACTIVE.md:1-2` | `release: v0.4.0` / `phase: IMPLEMENTATION` | schema v2 valid; phase stale |

PLAN.md is 216 lines (under the 300-line ceiling). ACTIVE.md carries no `segment:` line —
this is a flat, unsegmented release, consistent with the artifact layout.

### 1.2 Task completion vs what the code actually shows

16 of 16 tasks are `[x]`. Four workstreams spot-checked against the tree:

| Task | Claim | Verified on disk | Verdict |
|---|---|---|---|
| **T-A.1 / T-A.2** | 5 producer task-defs + services removed from `prd/07_ecs`; `common_stream_env`, `kinesis_sqs` and `dynamodb` remote-state sources gone; `migrar_kafka` comment gone | `grep -rn 'mined_blocks_watcher\|orphan_blocks_watcher\|block_data_crawler\|mined_txs_crawler\|txs_input_decoder\|common_stream_env\|kinesis_sqs\|migrar_kafka' services/prd/07_ecs/` → **no matches**. `ecs.tf` now declares only cluster (`:4`), capacity providers (`:15`), log group (`:28`), Cloud Map namespace (`:37`), and both ECR repos (`:60`, `:72`) | **CONFIRMED** |
| **T-C.1..C.4** | kinesis+sqs modules removed, `firehose_enabled = false` on all three peripherals stacks; kinesis/sqs/firehose outputs removed | `services/dev/01_peripherals/main.tf:81`, `services/hml/04_peripherals/main.tf:142`, `services/prd/04_peripherals/peripherals.tf:94` all carry `firehose_enabled = false`; all three `outputs.tf` grep clean for kinesis/sqs/firehose | **CONFIRMED** |
| **T-D.1** | `services/modules/{kinesis,sqs}` deleted | `ls services/modules/` → `cloudwatch_logs dynamodb ecs iam lambda s3 vpc` (7, no kinesis/sqs) | **CONFIRMED** |
| **T-D.3** | `S3_PRESERVED_TARGETS` drops kinesis/sqs, keeps dynamodb+cloudwatch_logs, warning comment added | `scripts/ci/destroy_env.sh:82` = `"-target=module.dynamodb -target=module.cloudwatch_logs"`; whole-env-teardown warning at `:74-75` | **CONFIRMED** |
| **T-D.4 / T-D.5** | 5 producer names purged from `scripts/` | `grep -rn 'mined-blocks-watcher\|orphan-blocks-watcher\|block-data-crawler\|mined-txs-crawler\|txs-input-decoder' scripts/` → **no matches** | **CONFIRMED** |

The implementation is real. No task claims a deliverable that is not on disk. That is worth
stating plainly, because everything below is about what the release did *not* cover.

### 1.3 What is missing to close (per `dd-release-closure`: memory → CLOSURE → archive)

1. **Memory update** — SPEC §8 (`SPEC.md:310-324`) pre-declares exactly four atoms to
   rewrite at CLOSURE (`capture-layer.md`, `tech-stack.md`, `aws-resources.md`,
   `index.md`+`catalog.json`). None has been touched; §2 of this report shows the drift is
   wider than SPEC §8 anticipated (`architecture.md` is the largest offender and is not on
   the SPEC's list).
2. **CLOSURE.md** — must carry `## Validations` evidence triples, a `## Drifts` section
   (T-4.1's mechanism substitution, SDD-08, belongs there), `## Memory updates`, and a
   `## Dispositions` sweep. The Dispositions sweep is currently **blocked** by the misfiled
   open bug (SDD-27) and by the two undispositioned prior audits (§4).
3. **Archive** — `git mv specs/releases/v0.4.0 specs/_archive/releases/v0.4.0`, then free
   `ACTIVE.md` to `release: none`.
4. **Branch** — `feature/v0.4.0` → `develop` is a **fast-forward** (`git rev-list
   --left-right --count HEAD...origin/develop` = `107  0`), then a diff-based
   `security-reviewer` verdict, then push `develop`. The local ahead-1 commit `c6feb17` is
   unpushed.

### 1.4 Archive directory inventory

`specs/_archive/releases/` — **8 releases, all 8 carry `CLOSURE.md` with `**Status:** Aprovado`.**

| Release dir | SPEC | PLAN | TASKS | CLOSURE | Notes |
|---|---|---|---|---|---|
| `pipeline-restart-r1` | ✓ | ✓ | ✓ | ✓ Aprovado | |
| `cost-and-availability-r2` | ✓ | ✓ | ✓ | ✓ Aprovado | forensic closure (abandoned) |
| `data-quality-r3` | ✓ | ✓ | ✓ | ✓ Aprovado | forensic closure (abandoned) |
| `analytics-enrichment-r4` | ✓ | ✓ | ✓ | ✓ Aprovado | forensic closure (abandoned) |
| `audit-remediation-r5` | ✓ | ✓ | ✓ | ✓ Aprovado | remediation for audit `20260609T013037Z` |
| `capture-decoupling-r5` | ✓ | ✓ | ✓ | ✓ Aprovado | **duplicate r5 ordinal**; also carries a stray `SPEC.handoff.json` |
| `legacy` | ✓ | — | — | ✓ Aprovado | SPEC status is non-canonical `Implementado` |
| `v0.3.0` | ✓ | ✓ | ✓ | ✓ Aprovado | |

Seven of the eight trigger `SPEC-DOC-027` (legacy naming vs `^v<MAJOR>.<MINOR>.<PATCH>$`).
Only `v0.3.0` is canon-named.

---

## 2. Memory staleness — per-atom verdicts

Ratings: **CURRENT** (matches code) · **PARTIAL** (mixed) · **STALE** (materially describes a
world that no longer exists).

### 2.1 Verdict table

| Atom | Rating | Headline |
|---|---|---|
| `specs/memory/architecture.md` | **STALE** | Entire "Capture Layer" architectural layer, its 5-job DAG, its data-flow diagram, its contracts table and 3 of 6 ADRs describe deleted infrastructure |
| `specs/memory/tech-stack.md` | **PARTIAL→STALE** | AWS Infrastructure and Module Inventory sections dead; Python/Databricks/Terraform/CI sections broadly accurate |
| `specs/memory/product/aws-resources.md` | **STALE** | Three whole sections (Kinesis, Firehose, SQS) inventory destroyed resources; ECS/ECR section wrong |
| `specs/memory/product/capture-layer.md` | **STALE (DEAD)** | The feature it documents no longer exists in this repo |
| `specs/memory/product/index.md` | **PARTIAL** | Catalog table lists a deleted feature at rank 1 and omits an existing atom; capability map diagram dead |
| `specs/memory/product/catalog.json` | **PARTIAL** | rank-1 and rank-2 entries stale; schema-retired keys retained; contradicts `index.md` |
| `specs/memory/product/cicd-pipeline.md` | **CURRENT** | Verified accurate against `.github/workflows/` and `scripts/ci/` |
| `specs/memory/product/medallion-pipelines.md` | **PARTIAL** | Accurate for Databricks; one upstream sentence assumes a live capture layer |
| `specs/memory/product/serving-layer.md` | **CURRENT** | No capture dependency; Databricks-side accuracy is the Databricks lane's call |
| `specs/memory/product/data-catalog.md` | **CURRENT** (this lane) | Pure Databricks inventory — defer to the Databricks lane; 10 heading-allowlist warnings |
| `specs/memory/quality-assurance.md` | **PARTIAL** | Test count drifted; documented CI gap still real |

### 2.2 `architecture.md` — **STALE**

| Line | Claim | Actual |
|---|---|---|
| `:5` | `tldr: ... 5-job ECS capture ...` | zero ECS task definitions or services exist; `services/prd/07_ecs/ecs.tf` declares cluster + ECR only |
| `:20` | "four architectural layers: (1) Capture Layer — 5 Python jobs on ECS Fargate" | layer deleted from IaC by T-A.1 |
| `:26` | Layer table: "Capture Layer \| 5 Python Docker jobs on ECS Fargate; ... deliver to Kinesis/Firehose/SQS" | all three services destroyed 2026-06-22 (`TASKS.md:178-188`) |
| `:27` | "S3 Raw Layer ... Firehose delivers here" | no Firehose exists; delivery is now the external `dd-chain-capture` VPS |
| `:33-77` | End-to-end Mermaid flow with J1–J5, Kinesis and Firehose edges | entirely fictional |
| `:83-89` | Per-job replica/input/output table (Job 4 ×6, Job 5 ×3) | no ECS services deployed |
| `:96-101` | IAM table granting SQS/Kinesis/Firehose to the ECS task role | grants still in `services/prd/03_iam/iam.tf:57-92` but for **destroyed** resources (see SDD-05) |
| `:157` | "Streaming apps \| PRD: ECS Fargate (persistent)" | none |
| `:196-199` | Contracts table: Job1→Job2 SQS, Job4→Job5 Kinesis, Job3/5→S3 Firehose | all dead |
| `:209` | Runtime state: "`services/prd/04_peripherals/` — Kinesis, Firehose, SQS, DynamoDB, S3" | `peripherals.tf` now declares only 3× s3, cloudwatch_logs, dynamodb (`:11,:31,:55,:86,:101`) |
| `:214-220` | **ADR-001** ("Use Kinesis Data Streams + Firehose Direct Put as the event bus") and **ADR-002** ("Firehose Direct Put vs Kinesis Intermediary") | superseded by the capture retirement; no superseding ADR was ever written (this is backlog WS-E/E1, still open) |
| `:234-236` | **ADR-006** distributed API-key rotation across 6 Job-4 replicas | no replicas exist |

`architecture.md` is **not** on SPEC §8's CLOSURE list. It is the single largest memory
liability and must be added.

### 2.3 `tech-stack.md` — **PARTIAL→STALE**

| Line | Claim | Actual |
|---|---|---|
| `:5-6` | frontmatter tldr/summary name "Kinesis/Firehose/SQS" as stack pillars | destroyed |
| `:76` | "ECS Fargate \| 5 task definitions (1+1+1+6+3 replicas)" | zero |
| `:77` | "ECR \| `onchain-stream-txs` repository" | **two** repos declared: `aws_ecr_repository.stream` and `.batch` (`services/prd/07_ecs/ecs.tf:60,72`) |
| `:78-80` | Kinesis / Kinesis Firehose / SQS rows | destroyed |
| `:85` | "CloudWatch Logs \| Application JSON logs → Firehose → S3" | `firehose_enabled = false` on all three stacks; the subscription filter and both IAM roles were destroyed |
| `:152` | Module inventory: `kinesis` \| `services/modules/kinesis/` | **directory deleted** (T-D.1) |
| `:155` | Module inventory: `sqs` \| `services/modules/sqs/` | **directory deleted** (T-D.1) |
| `:148` | "`cloudwatch_logs` \| Log groups with Firehose integration" | integration disabled everywhere |
| `:167` | "Integration tests \| 4 Bash scripts in `scripts/`" | **5** on disk (`dev_dlt`, `dev`, `hml_dlt`, `hml`, `hml_optimized`) |
| `:61-63` | dm-chain-utils exports `KinesisHandler`, `SQSHandler`, `FirehoseHandler` | still true in the library (OQ-5 deliberately out of scope) — **CURRENT**, keep |
| `:139-142`, `:160-192` | Terraform ≥1.5/CI 1.7.0, 7 workflows, 18 `scripts/ci` bash helpers, OIDC 4-role matrix, single-source stack map | **verified CURRENT**: `ls .github/workflows/` = 7; `ls scripts/ci/*.sh` = 18 |

### 2.4 `product/aws-resources.md` — **STALE**

| Line | Claim | Actual |
|---|---|---|
| `:5-6`, `:12-13` | tldr/summary/tags lead with Kinesis, Firehose, SQS | destroyed |
| `:92-100` | **Kinesis Data Streams** section — 3 streams incl. a `-hml` stream | destroyed (dev/prd); hml never existed (`SPEC.md:51`) |
| `:104-116` | **Kinesis Firehose** section — 5 named streams + PRD equivalents | destroyed |
| `:120-131` | **SQS Queues** section — 6 queues + DLQs | destroyed |
| `:167` | "ECR Repository \| `onchain-stream-txs` \| Docker image for all 5 streaming jobs" | 2 repos; no jobs deployed |
| `:168` | "ECS Services (PRD) \| 5 services (jobs 1–5)" | zero |
| `:174-178` | CloudWatch table — every log group has a "Firehose Subscription" | all subscription filters destroyed |
| `:189` | ECS Task Role "Container runtime access: ... SQS, Kinesis, Firehose" | IAM code still says so (SDD-05); the targets do not exist |
| `:201` | State path comment "`dev/peripherals` # S3, Kinesis, SQS, Firehose, DynamoDB, CloudWatch" | now S3 + DynamoDB + CloudWatch only |
| `:63-70` | S3 bucket inventory (8 buckets) | survives v0.4.0 (S3 is the declared boundary) — but the **2026-08-19 recap #3** reports the lakehouse/databricks bucket roles are inverted live; **needs-live-recheck by the AWS lane** |

### 2.5 `product/capture-layer.md` — **STALE (DEAD)**

The whole atom documents a retired feature. Every section is dead: `:5-6` frontmatter,
`:19-23` Propósito, `:36-40` the five-step flow, `:44` "runs 24/7 ... < 2 minutes latency",
`:52-59` runtime state (SQS/Kinesis/Firehose resources), `:64` dependency on
"ECS cluster, ECR, DynamoDB, Kinesis, Firehose, SQS".

One nuance: `:25-32` (logger injection, 71 unit tests, `_key_ref()` CWE-532 posture) still
describes **source code that is still in the tree** — `apps/docker/onchain-stream-txs/src/1..5_*.py`
and `tests/unit/` were never deleted; only their ECS deployment and AWS peripherals were.
SPEC §8 offers the operator a choice — rewrite the atom around the S3 boundary +
`dd-chain-capture` pointer, or archive it to `_archive/legacy-memory/`. **That decision is
still open** and is a genuine product-engineer/operator call, not an auditor call. Note that
`:27` says "71 unit tests"; the disk has **78** across the same 6 `test_*.py` files.

### 2.6 `product/index.md` — **PARTIAL** · `catalog.json` — **PARTIAL** (mutually CONTRADICTORY)

- `index.md:32` lists `capture-layer` **first** in the feature catalog; `catalog.json:31-33`
  ranks it **2**. Both point at a retired feature.
- `catalog.json:11-13` — `aws-resources` tldr/summary/tags still lead with Kinesis/Firehose/SQS.
- **Contradiction:** `index.md:30-36` lists **5** features; `catalog.json` carries **6**
  (`cicd-pipeline`, rank 6, is missing from `index.md`). The two indices of the same catalog
  disagree.
- `catalog.json:110` — `cicd-pipeline`'s `path` is `"product/cicd-pipeline.md"` while the other
  five use the `"specs/memory/product/<slug>.md"` form. Inconsistent path convention.
- `catalog.json` retains `token_estimate` and `agent_tier` on all six entries (`:26-27`, `:45-46`,
  `:66-67`, `:86-87`, `:105-106`, …) — the very keys commit `c6feb17` stripped from every atom's
  frontmatter ("strips the schema-retired `agent_tier` and `token_estimate` keys from every
  memory atom"). The pattern-5 migration did not reach `catalog.json`.
- `catalog.json:2` — `generated_at: 2026-06-11`, i.e. never regenerated across v0.4.0.
- `index.md:40-49` — the capability-map Mermaid still routes `ETH → CL["Capture Layer\n5 ECS Jobs"] → S3`.

### 2.7 `product/medallion-pipelines.md` — **PARTIAL**

Databricks content is intact. `:24` ("processes CloudWatch application logs from the 5
streaming jobs") and `:28` ("S3 raw data lands ... Firehose delivery, hourly partitioned")
both assume a live capture layer. One-sentence corrections at CLOSURE.

### 2.8 `quality-assurance.md` — **PARTIAL**

- `:6`, `:21` — "71 streaming-job unit tests" → disk has **78** `def test_` across the same 6
  files in `apps/docker/onchain-stream-txs/tests/unit/`. `:22` "35" utils tests → **35 CONFIRMED**.
- `:24-27` — describes coverage of "each of the 5 streaming job classes"; those classes are
  now undeployed. The tests are alive; the surface they guard is retired. Pruning/demotion is a
  `qa-engineer` verdict, not this lane's.
- `:31-33` — "CI runs **only** the utils suite ... the 71 streaming-job tests are not wired into
  any workflow" → **STILL TRUE**: the only pytest invocation in the repo is
  `.github/workflows/deploy_all_dm_applications.yml:163` (`pytest ${{ env.UTILS_DIR }}/tests/unit/`).
  Backlog item WS-F5 remains open and correctly stated.

### 2.9 `product/cicd-pipeline.md` — **CURRENT**

Verified: 7 workflows named at `:21-23` match `ls .github/workflows/` exactly; `:77`
"18 Bash helpers + `changed_stacks.py` + `stack_map.json`" matches disk. The informed-gate
and OIDC descriptions match `deploy_env.sh` / `plan_gate_check.sh` structure. One caveat
outside this lane: the recap reports CI has been dormant since 2026-04-11, so "current" here
means *code-accurate*, not *operationally exercised*.

---

## 3. Backlog inventory

Seven loose files, **no `BACKLOG.md`**, **no `specs/backlog/_archive/`** — 7× `SPEC-DOC-035` +
1× `SPEC-DOC-034`. Pattern-5 canon requires a single `BACKLOG.md` with `## ACTIVE` + `## LEDGER`.
The folding is `project-manager` work; this is the inventory it will need.

| File | Items | Classification |
|---|---|---|
| `ideas.md` | 0 | **empty boilerplate** — "(Sem ideias registradas ainda.)". Fold as an empty section or drop. |
| `remediation-audit-20260609.md` | BL-01 … BL-07 | **all done-by-audit-remediation-r5/v0.3.0.** Each maps 1:1 to a bug closed in `v0.3.0/CLOSURE.md §Dispositions`. **Whole file is LEDGER material.** |
| `candidates.md` | LOW-1..4, INV-1..3, GAP-LD-1..6, OQ-1..7 | **mixed / partially superseded.** LOW-1 + LOW-2 marked RESOLVED inline; GAP-LD-1 closed at v0.3.0 (`cicd-pipeline.md` authored); OQ-1..7 are a settled 2026-05-22 decision record (LEDGER). LOW-4 (ECS right-sizing) and INV-1 (PRD deploy sequence) are **obsolete-by-capture-retirement**. INV-2 (REST API) + INV-3 (DynamoDB TTL) + LOW-3 + GAP-LD-2..6 remain **open**. |
| `rebuild-abandoned-r2-r3-r4-capabilities.md` | CAND-R2-01..08, R3-01..06, R4-01..09 (23) | **partly obsolete.** Obsolete-by-capture-retirement: **CAND-R2-01** (Kinesis→ON_DEMAND), **CAND-R2-03** (Firehose buffer), **CAND-R2-05** (FARGATE_SPOT per producer service), **CAND-R2-07** (rebuild producer image + redeploy ECS). Partly obsolete: **CAND-R2-02** (cluster default capacity provider — cluster survives, no services). Still open: R2-04/06/08, all of Group B (R3-01..06, Databricks), all of Group C (R4-01..09, Databricks/serving). |
| `streaming-jobs-security-hardening.md` | SEC-HARD-04..10, TEST-HARD-01/02 (9) | **wholly obsolete-by-capture-retirement as *deployed* risk** — every finding cites `4_mined_txs_crawler.py`, `5_txs_input_decoder.py`, `utils_decode/etherscan_multi.py` or the producer `Dockerfile`; none of that is deployed anywhere in this repo any more. The **source still exists in-tree**, so these are source-hygiene items, not runtime risk. Two (SEC-HARD-05/F-05, SEC-HARD-10/D-01) touch `utils_decode/` which may migrate with `dd-chain-capture` — operator call on ownership. |
| `platform-audit-remediation-20260611.md` | WS-A..WS-G (~30 items over 5C/17H/28M/20L) | **the live epic.** CONSUMED by v0.3.0: WS-A (A1..A7), WS-B1/B2/B3. **Partially executed by v0.4.0 without ever being picked**: WS-E/E2 ("dead-code/infra removal wave") — v0.4.0 removed the ECS/Kinesis/SQS/Firehose surface but **WS-E/E1 (the formal deprecation ADR) was never written**, and WS-E/E3 (dangling `contracts_ingestion` producer) is now *worse*, not better (recap #4: hourly no-op). Still open: WS-B4/B5/B6, WS-C (C1 stale PRD Databricks monolith, C2 HML-validates-PRD, C3 Makefile), WS-D (D1..D5), WS-E/E1/E3, WS-F (F1..F7), WS-G (G1 working-tree pollution, G2 branch model). |
| `v0.3.0-operator-cutover-and-next.md` | WS-1 (8 operator items), WS-2 (3 cleanups), WS-3 (GAP-LD-2..6) | **open, high-consequence.** WS-1 items 1–8 (Infura key rotation OP-R6-1, OIDC provider, 03_iam apply, hml required_reviewers, 4-role evidence, live OIDC validation, hml graduation, static-key deletion OP-R6-4) are all still pending per the recap's "CI dormant since 2026-04-11". **WS-3 duplicates `candidates.md` GAP-LD-2..6.** |

**Duplicates to collapse when folding:** GAP-LD-2..6 (in `candidates.md` §"Memory gaps" *and*
`v0.3.0-operator-cutover-and-next.md` WS-3); WS-C/C3 Makefile retirement ↔ `candidates.md`
Makefile mentions; `remediation-audit-20260609.md` BL-04/BL-05 ↔ bugs `drift-01`/`bp-01`
(both Closed).

---

## 4. Prior audits — validity and archivability

**Governing law (`DADAIA.md` §5 Audits):** one audit generates exactly one remediation release;
that release gives **every** finding an explicit disposition; the audit archives to
`specs/audits/_archive/` only once fully dispositioned, and names that release.

### 4.1 `specs/audits/20260609T013037Z/` — score 6.2/10, 9 drift items

- **Remediation release:** `audit-remediation-r5` (archived, CLOSURE Aprovado), completed by
  `v0.3.0`.
- **Disposition trail:** the audit's items were compiled into
  `specs/backlog/remediation-audit-20260609.md` as BL-01..BL-07, each mapped 1:1 to a bug;
  `v0.3.0/CLOSURE.md §Dispositions` closes **all 8 bugs** with evidence
  (`c789e9c`, `226740e`, `cb218f7`, T-R6-S3/S4/S5/S6).
- **Verdict: FULLY DISPOSITIONED → ARCHIVABLE NOW.** `SPEC-DOC-038`'s warning on this dir is
  **correct**. Blocker: `specs/audits/_archive/` does not exist (`SPEC-DOC-034`, auto-fixable).
  It must be archived *naming* its remediation release (`audit-remediation-r5` + `v0.3.0`).
- Secondary: the dir name `20260609T013037Z` lacks the `-<session_id_8>` suffix
  (`SPEC-DOC-030`). Rename on archive.

### 4.2 `specs/audits/20260611T001412Z-cb56f84c/` — 5 CRITICAL / 17 HIGH / 28 MEDIUM / 20 LOW

- **Remediation release:** `v0.3.0` consumed only the **WS-A + WS-B1/B2/B3 slice**.
- **Disposition trail:** `v0.3.0/CLOSURE.md §Dispositions` contains **no per-finding token for
  any of the 70 findings**. Its only backlog row reads
  *"`platform-audit-remediation-20260611.md` | backlog | **non-terminal (CANDIDATE)** — WS-A +
  B1/B2/B3 slice CONSUMED by v0.3.0; WS-B4/B5/B6, WS-C/D/E/F/G remain candidate"*.
- **Verdict: NOT DISPOSITIONED → NOT ARCHIVABLE.** `SPEC-DOC-038`'s warning on this dir is a
  **false positive under the law** — the audit is correctly loose because it is unresolved.
  All 5 CRITICALs (ARCH-C1 split-brain PRD Databricks, ARCH-C2 HML-doesn't-validate-PRD,
  CI-C1/C2/C3) remain open two months later. This is the largest undischarged governance debt
  in the repo, and it **blocks a compliant v0.4.0 CLOSURE Dispositions sweep**.
- Note ARCH-H5 called out *"the capture layer as a whole is superseded by the sibling
  `dd-chain-capture` repo with **no deprecation ADR**"* — v0.4.0 executed the removal but still
  never wrote the ADR (WS-E/E1). The finding is *more* valid now, not less.

### 4.3 Recap audit handoff `2026-08-19T002955Z-project-auditor-full-recap-audit.handoff.json`

Its 10 findings, triaged against today's tree. Live-AWS/Databricks claims are marked for the
lanes that own them; I re-verified only the on-disk half.

| # | Sev | Finding | This lane's verdict |
|---|---|---|---|
| 1 | HIGH | v0.4.0 done-but-open: no CLOSURE, memory stale, branch unmerged/ahead-1 | **STILL VALID — re-confirmed** (`ACTIVE.md:2` phase=IMPLEMENTATION; no `CLOSURE.md`; atoms unchanged since `c6feb17`; `origin/feature/v0.4.0` ahead 1) |
| 2 | HIGH | S3 boundary DRY — `raw-data` empty, last data 2026-05-23, DLT idle | **NEEDS-LIVE-RECHECK** (live AWS + Databricks lanes) |
| 3 | MED | PRD app-logs Firehose delivered into the **lakehouse** bucket, not raw-data | **NEEDS-LIVE-RECHECK** for the live half; the **memory half is STILL VALID** — `aws-resources.md:65` describes lakehouse as "checkpoints, staging, unity-catalog prefixes only — no medallion layer prefixes", which the recap says is inverted live |
| 4 | MED | PRD `contracts_ingestion` runs 24×/day processing 0 contracts | **NEEDS-LIVE-RECHECK**; code half STILL VALID — the lambda + hourly EventBridge rule are still declared (`services/prd/06_lambda/`), and this is backlog WS-E/E3 ("dangling producer") unresolved |
| 5 | MED | Live orphans outside any TF state (ChainExplorer-vpc, hml ECS shell, legacy dev lambda, log groups) | **NEEDS-LIVE-RECHECK** (live AWS lane) |
| 6 | MED | Stale-ahead TF state: hml/peripherals claims dead buckets; hml/iam manages 19 live IAM resources | **NEEDS-LIVE-RECHECK**; code half **CORROBORATED** — `services/hml/03_iam/main.tf:91-123` still creates `dm-chain-explorer-firehose-role-hml` + a kinesis read policy, and `outputs.tf:9` still exports `firehose_role_arn` (see SDD-05) |
| 7 | INFO | PRD Databricks workspace does not exist; Free Edition is the only runtime | **NEEDS-LIVE-RECHECK**; the **memory contradiction is STILL VALID** — `tech-stack.md:110` and `architecture.md:158` both assert "Unity Catalog enforced in PRD / Databricks Workspace (`dd_chain_explorer` catalog)" |
| 8 | INFO | `drift_detection` cron has NEVER fired — workflow absent from the default branch | **STILL VALID — re-confirmed this session.** `git ls-tree origin/master -- .github/workflows/` returns 7 files **without** `drift_detection.yml` or `plan_on_pr.yml`; both exist on `origin/develop`. GitHub fires `schedule:` only from the default branch, and the default branch is `master`. Corollary: **AC-7 of v0.4.0 is structurally unsatisfiable** as written |
| 9 | INFO | `dd-chain-capture` ECR/IAM/KMS terraform state lives in this repo's state bucket, undocumented | **NEEDS-LIVE-RECHECK**; the **documentation gap is STILL VALID** — no memory atom mentions it |
| 10 | INFO | SSM holds 17 infura + 4 alchemy + 6 etherscan keys; only 1 consumed | **NEEDS-LIVE-RECHECK**; ownership question compounds open item OP-R6-1 (Infura key rotation, an **accepted risk since 2026-06-11**) |

**Zero of the 5 `decisions_required` from 2026-08-19 have been actioned in the four days since.**

---

## 5. Git / branch governance drift

**Law (`DADAIA.md` §5):** exactly four branch patterns — `main` (remote+local, PR-only from
`develop`), `develop` (the only pushable branch), `feature/{M.m.p}`, `hotfix/{M.m.p}`.

| Reality | Law | Delta |
|---|---|---|
| Default branch = `master` (`origin/HEAD -> origin/master`) | `main` | **fifth pattern**; `main` does not exist |
| `develop` exists, is an **ancestor** of `feature/v0.4.0` (`107  0`) | develop is the integration branch | merge is a clean fast-forward — good |
| `master` is `192` ahead / `4` behind `feature/v0.4.0` | `main` advances only via PR from `develop` | **divergent legacy trunk**: master carries `deploy_dm_applications.yml` + `lib_release.yml` that develop dropped, and lacks `drift_detection.yml` + `plan_on_pr.yml` that develop has |
| `feature/v0.4.0`, `feature/v0.3.0` | `feature/{M.m.p}` | conformant |
| `feature/specs-first-docs-cleanup` (local, **ahead 5 unpushed**) | — | non-conformant name + unpushed work |

**Stale remote branches (`git branch -r`) — 10 beyond the canon:**
`feature/devops-audit-remediation-2026-05`, `feature/dm-v4`, `feature/doc`,
`feature/lambda-tests-and-dry-run`, `feature/specs-first-docs-cleanup`,
`fix/cicd-ecs-timeout`, `fix/cicd-terraform-wrapper`, `fix/revert-direct-master-commit`,
`fix/sqs-polling-optimization`, `release/infra-v0.1.0`.
(`origin/feature/v0.3.0` and `origin/feature/v0.4.0` are canon-named but should retire once merged.)

**VERSION vs release id.** `VERSION` = `0.2.9`; the active release is `v0.4.0`; tags are
`v0.2.9`, `v0.2.9-infra`, `v0.2.9-dabs`, `v0.2.9-lambda`. These are **two distinct axes** —
`VERSION` drives the `dm-chain-utils` PyPI/layer artifact (`tech-stack.md:56` "Version synced
with root `VERSION` file"; `auto-bump-version.yml` bumps it on merge to develop), while the
release id is the SDD lineage. The split is defensible but **documented nowhere in memory**,
and `aws-resources.md:155` pins "`dm-chain-utils==0.2.9` installed as a Lambda layer", which
will silently drift the moment auto-bump fires. This is a naming-coherence gap, recorded, not
an error.

**Open bug.** `dadaia bugs status` → 1 open: `sdd-artifact-linter-mutates-task-markers` (HIGH).
Reading `specs/bugs/bugs.jsonl`, its `surface` is *"SDD artifact post-write linter (editing
`specs/releases/<id>/{SPEC,PLAN,TASKS}.md` via file tools)"* and its symptom is a post-write
linter mutating `[ ]`/`[-]`/`[x]` markers and `**Status:**` tokens between an Edit's Read and
apply. **That is a dadaia-workspace tooling/harness bug, not a dd-chain-explorer product bug.**
Per `dd-bug-registration` §5 it belongs in `repos/dadaia-workspace/specs/bugs/`. Ledger hygiene:
`drift-04`'s `resolved` event carries `release: "unknown"` and `ts: 2026-06-08`, *earlier* than
the closure evidence recorded in its own `reported` event (2026-06-11).

---

## 6. Findings table

| ID | Sev | Area | Finding | Evidence (file:line) | Recommended disposition |
|---|---|---|---|---|---|
| SDD-01 | HIGH | Release | v0.4.0 is implementation-complete (16/16 `[x]`, deliverables verified) but never closed: no `CLOSURE.md`, no memory update, phase still IMPLEMENTATION, branch unmerged + ahead-1 unpushed | `specs/releases/ACTIVE.md:1-2`; `specs/releases/v0.4.0/TASKS.md:20-201`; absent `specs/releases/v0.4.0/CLOSURE.md`; `git status -sb` → `[ahead 1]` | `product-engineer` runs memory→CLOSURE; `project-manager`/operator then ff-merge to `develop`, security-review the delta, push, archive |
| SDD-02 | MEDIUM | Dead code | The R2 reviewers' own recorded "non-blocking CLOSURE cleanups" were never executed: 4 dead symbols in `prd/07_ecs` + a misnamed remote-state alias in `06_lambda` | `services/prd/07_ecs/main.tf:37` (`remote_state "iam"` unconsumed); `locals.tf:5,6,18` (`ecr_image_stream`, `ecr_image_batch`, `log_config` unconsumed); `services/prd/06_lambda/main.tf:47` + `lambda_contracts_ingestion.tf:119` (alias `kinesis_sqs`); note recorded at `TASKS.md:170-172` | `software-engineer` in the remediation release |
| SDD-03 | HIGH | CI / regression vector | `deploy_all_dm_applications.yml` still provisions, asserts and tears down HML capture infrastructure — including `terraform destroy -target='module.kinesis'` on a stack that no longer declares it and a module that was deleted. `.github/workflows/` was in no v0.4.0 write set, so AC-6 never covered it | `.github/workflows/deploy_all_dm_applications.yml:257,293-294,326-327,366-370,539,559-566,785`; `scripts/ci/hml_provision.sh:28-36` (fetches destroyed SQS queue URLs); deleted module confirmed by `ls services/modules/` | `software-engineer` — this is the exact "streams come back" vector SPEC §3.2 targeted; must be closed before any app-deploy run |
| SDD-04 | MEDIUM | CI / change detection | `stack_map.json` lists `modules: []` for `dev/peripherals` and `dev/lambda` although those stacks consume `s3`+`dynamodb`+`cloudwatch_logs` and `lambda` — module-edit→dependent-stack detection is blind for DEV, so AC-7 cannot be honest for DEV | `scripts/ci/stack_map.json` (dev entries); vs `services/dev/01_peripherals/main.tf:46,65,74` and `services/dev/02_lambda/main.tf:97` | `software-engineer` — populate the DEV `modules` arrays |
| SDD-05 | MEDIUM | IaC / least privilege | IAM still grants and creates capture permissions for destroyed services. SPEC §4 scoped out "IAM (OIDC roles)" but never dispositioned the capture **task-role** grants | `services/prd/03_iam/iam.tf:57-92` (Kinesis/Firehose/SQS statements on `mainnet-*-prd`); `services/hml/03_iam/main.tf:91-123` (creates `dm-chain-explorer-firehose-role-hml` + kinesis policy); `outputs.tf:9` exports `firehose_role_arn` | `software-engineer` under a `security-reviewer` verdict; overlaps the security lane — coordinate, do not double-file |
| SDD-06 | LOW | Residue | Dev/ops surfaces still point at destroyed capture resources | `services/dev/00_compose/conf/dev.dynamodb.conf:13-20`; `Makefile:333-336,415`; `scripts/dev_dlt_integration_test.sh:127-131` | `software-engineer` in the remediation release |
| SDD-07 | INFO | Release evidence | T-4.1 records AC-0/AC-1/AC-3 verified but AC-4 (lambda functional invoke), AC-5 (batch ECS + ECR) and AC-7 (drift_detection zero + plan_on_pr clean) carry no evidence; AC-7 is structurally unsatisfiable while `drift_detection.yml` is absent from the default branch | `specs/releases/v0.4.0/TASKS.md:178-202` vs `SPEC.md:204-238`; `git ls-tree origin/master -- .github/workflows/` | Record honestly in `CLOSURE.md §Validations` — do not backfill unverified evidence |
| SDD-08 | INFO | Release drift | T-4.1 substituted a targeted `terraform destroy` for the SPEC-locked CI config-diff apply (OQ-4). Self-documented in the task, never folded back into SPEC §7 or recorded as a drift | `TASKS.md:178-188` vs `SPEC.md:296-306,359-361` | Record as a `## Drifts` entry in `CLOSURE.md` (`product-engineer`) |
| SDD-09 | LOW | Archive | `_archive/releases/legacy/SPEC.md` uses non-canonical status `Implementado` | `specs/_archive/releases/legacy/SPEC.md` (Status line) | Record-only — FROZEN path, never edit |
| SDD-10 | LOW | Archive | Duplicate `r5` ordinal (`audit-remediation-r5`, `capture-decoupling-r5`); 7 of 8 archived dirs are legacy-named (`SPEC-DOC-027`) | `dadaia specs doctor` × 7 | Record-only; renaming FROZEN dirs is not worth the churn |
| SDD-11 | LOW | Hygiene | A handoff JSON lives inside `specs/` instead of `.dadaia/handoff/` | `specs/_archive/releases/capture-decoupling-r5/SPEC.handoff.json` | Record-only (FROZEN) |
| SDD-12 | HIGH | Memory | Every capture-describing atom is STALE/DEAD — see §2 for ~40 cited claims across `architecture.md`, `tech-stack.md`, `aws-resources.md`, `capture-layer.md`, `index.md`, `catalog.json`. `architecture.md` is the worst offender and is **not** on SPEC §8's CLOSURE list | `architecture.md:5,20,26,27,33-77,83-89,157,196-199,209,214-220,234-236`; `tech-stack.md:5-6,76-80,85,148,152,155`; `aws-resources.md:5-6,92-131,167-168,174-178,201`; `capture-layer.md` (whole) | `product-engineer` in the v0.4.0 CLOSURE window — **add `architecture.md` to the SPEC §8 list**. Operator decides capture-layer rewrite-vs-archive |
| SDD-13 | MEDIUM | Memory | `index.md` and `catalog.json` disagree on the catalog: 5 features vs 6 (`cicd-pipeline` missing from `index.md`) | `specs/memory/product/index.md:30-36` vs `catalog.json` (rank 6) | `product-engineer` at CLOSURE |
| SDD-14 | LOW | Memory | `catalog.json` path convention inconsistent — one entry uses `product/…`, five use `specs/memory/product/…` | `specs/memory/product/catalog.json:110` | `product-engineer` at CLOSURE (or regenerate) |
| SDD-15 | LOW | Memory / migration | `catalog.json` still carries `token_estimate` + `agent_tier` on all 6 entries — the keys `c6feb17` stripped from every atom; `generated_at` frozen at 2026-06-11 | `catalog.json:26-27,45-46,66-67,86-87,105-106`; commit message of `c6feb17` | Regenerate the catalog at CLOSURE (`dadaia memory catalog generate`) |
| SDD-16 | LOW | Memory | Test count stale: memory says 71 streaming unit tests, disk has 78 across the same 6 files | `quality-assurance.md:6,21` and `capture-layer.md:27` vs `grep -c 'def test_' apps/docker/onchain-stream-txs/tests/unit/*.py` → 78 | `product-engineer` at CLOSURE |
| SDD-17 | LOW | Memory | `tech-stack.md` undercounts: "4 Bash integration tests" (5 on disk); "ECR \| `onchain-stream-txs` repository" (2 repos declared) | `tech-stack.md:167,77` vs `ls scripts/*integration_test*.sh`; `services/prd/07_ecs/ecs.tf:60,72` | `product-engineer` at CLOSURE |
| SDD-18 | MEDIUM | Governance | `specs/constitution.md` is a 33-byte frontmatter stub carrying **no product law** — the primary audit anchor per `dd-audit-project`. The 231-line pre-onboarding constitution survives only in the archive. Peer contexts carry real ones (dadaia-workspace 14 KB, tauan-games 5 KB) | `specs/constitution.md` (3 lines, `specs_pattern_version: 5` only); `specs/_archive/legacy-memory/20260609T003851Z/constitution.md` (231 lines); origin traced to `129c120`, **not** the pattern-5 migration | Operator decision → `product-engineer` authors a real constitution, or the operator ratifies "no constitution" explicitly |
| SDD-19 | INFO | Upstream library | `specs/memory/AGENTS.md` (a manifest-tracked projection of `scaffold/memory/AGENTS.md`) still mandates `agent_tier` + `token_estimate` frontmatter that pattern-5 strips — projected law contradicts projected data | `specs/memory/AGENTS.md:44`; `.dadaia/agentic/manifest.json` → `scaffold/memory/AGENTS.md` | Route to `ai-engineer`; register in `repos/dadaia-workspace/specs/bugs/` — **not** a dd-chain-explorer defect |
| SDD-20 | MEDIUM | Backlog | 7 loose files, no `BACKLOG.md` (ACTIVE+LEDGER), no `specs/backlog/_archive/` | 7× `SPEC-DOC-035` + `SPEC-DOC-034` from `dadaia specs doctor` | `project-manager` folds per `dd-backlog-definition`; §3 above is the inventory |
| SDD-21 | MEDIUM | Backlog | Obsolete-by-capture-retirement items still sitting in ACTIVE-equivalent state | `rebuild-abandoned-r2-r3-r4-capabilities.md` CAND-R2-01/03/05/07; `platform-audit-remediation-20260611.md` WS-B4; all 9 of `streaming-jobs-security-hardening.md`; `candidates.md` LOW-4 + INV-1 | `project-manager` — each needs a LEDGER line with disposition + reason; nothing is deleted |
| SDD-22 | LOW | Backlog | Duplicates and fully-done files not yet retired to LEDGER | GAP-LD-2..6 in both `candidates.md` §Memory gaps and `v0.3.0-operator-cutover-and-next.md` WS-3; all of `remediation-audit-20260609.md` (BL-01..07 closed at v0.3.0) | `project-manager` at fold time |
| SDD-23 | HIGH | Audits | Audit disposition law unsatisfied. `20260609T013037Z` is fully dispositioned and **archivable now** (blocked only by the missing `_archive/`). `20260611T001412Z-cb56f84c` has **zero per-finding dispositions** — all 5 CRITICALs open two months on — and is correctly **not** archivable | `v0.3.0/CLOSURE.md §Dispositions` (bugs only + one non-terminal backlog row); `platform-audit-remediation-20260611.md:1-16`; `dadaia specs doctor` `SPEC-DOC-038` ×2, `SPEC-DOC-034` | `project-manager` compiles an operator intake report; the 20260611 audit needs **one** remediation release that dispositions every finding. Archive 20260609 naming `audit-remediation-r5` + `v0.3.0` |
| SDD-24 | MEDIUM | Git | Branch model off-canon: default branch is `master` (no `main`); `master` is divergent (192 ahead / 4 behind) and carries a different workflow set than `develop`. Direct consequence: the `drift_detection` cron has never fired (recap #8, re-confirmed) | `git symbolic-ref refs/remotes/origin/HEAD` → `origin/master`; `git rev-list --left-right --count HEAD...origin/master` → `192 4`; `git ls-tree origin/master -- .github/workflows/` lacks `drift_detection.yml`/`plan_on_pr.yml` | Operator decision (recap decision #5), then `software-engineer`/devops. Also backlog WS-G/G2 |
| SDD-25 | LOW | Git | 10 stale non-canonical remote branches; `feature/specs-first-docs-cleanup` is local-ahead-5 unpushed | `git branch -r`; `git branch -vv` | Operator decision — never delete a branch on presumption of merge; verify contents first |
| SDD-26 | LOW | Versioning | Two undocumented version axes: `VERSION`=0.2.9 (dm-chain-utils artifact, auto-bumped, tagged `v0.2.9*`) vs release id `v0.4.0` (SDD lineage). `aws-resources.md:155` hard-pins `dm-chain-utils==0.2.9` and will drift on the next auto-bump | `VERSION`; `git tag`; `tech-stack.md:56`; `aws-resources.md:155`; `.github/workflows/auto-bump-version.yml` | `product-engineer` documents both axes in `tech-stack.md` at CLOSURE |
| SDD-27 | MEDIUM | Bugs | The single open bug is a **dadaia-workspace tooling bug misfiled in this repo's ledger** — its surface is the SDD artifact post-write linter, not any dd-chain-explorer artifact. It also blocks a clean v0.4.0 Dispositions sweep | `specs/bugs/bugs.jsonl` → `sdd-artifact-linter-mutates-task-markers`, `surface: "SDD artifact post-write linter (editing specs/releases/<id>/{SPEC,PLAN,TASKS}.md via file tools)"`; routing law: `dd-bug-registration` §5 | Re-register under `repos/dadaia-workspace/specs/bugs/` (`ai-engineer` owns the linter surface); dispose the dd-chain-explorer entry as `superseded`/`misfiled` with the pointer. Operator ratifies |
| SDD-28 | LOW | Bugs | Ledger inconsistency: `drift-04`'s `resolved` event carries `release: "unknown"` and a timestamp (2026-06-08) *earlier* than the closure evidence in its own `reported` event (2026-06-11) | `specs/bugs/bugs.jsonl` (`drift-04-kafka-avro-dead-code`, resolved event) | Record-only; correct on the next ledger touch |
| SDD-29 | MEDIUM | Hygiene | Working-tree pollution violating `DADAIA.md` §4 "repos stay clean": `apps/docker/onchain-stream-txs/.hypothesis/` plus 16 `apps/dabs/*/.databricks/` trees containing nested `.terraform/`. Untracked, but present. Duplicate test trees `test/` + `tests/` under the streaming app | `find` results (17 dirs); `git ls-files` confirms none are tracked; backlog `platform-audit-remediation-20260611.md` WS-G/G1 | `software-engineer` — clean recipe + gitignore; gitignore alone is not compliance |

---

## 7. Dead / stale code (SDD lane)

| Item | Evidence | Note |
|---|---|---|
| `data "terraform_remote_state" "iam"` in `prd/07_ecs` | `services/prd/07_ecs/main.tf:37` — zero `remote_state.iam` consumers in the stack | Orphaned by T-A.1 |
| `local.ecr_image_stream`, `local.ecr_image_batch`, `local.log_config` | `services/prd/07_ecs/locals.tf:5,6,18` — zero consumers (`local.common_tags` **is** consumed) | Orphaned by T-A.1 |
| ECR repo `aws_ecr_repository.batch` (`onchain-batch-txs`) | `services/prd/07_ecs/ecs.tf:72`; no `apps/docker/onchain-batch-txs/` source exists (only `onchain-stream-txs`) | Phantom target — OQ-1 kept it for "the surviving batch workload"; that workload has no source in this repo. **Needs the live/code lanes to confirm** before any removal |
| 5 producer job sources + their 78 tests | `apps/docker/onchain-stream-txs/src/{1..5}_*.py`, `tests/unit/` | Alive in-tree, deployed nowhere. Retain-vs-migrate-to-`dd-chain-capture` is an operator decision; test pruning is a `qa-engineer` verdict |
| `apps/docker/onchain-stream-txs/test/test_server.py` | duplicate of the `tests/` tree | Backlog WS-G/G1 |
| HML capture provisioning lane | `.github/workflows/deploy_all_dm_applications.yml:257-370,539-566,785`; `scripts/ci/hml_provision.sh:28-36` | **Not merely dead — actively broken and re-provisioning** (SDD-03) |
| Legacy `_archive/legacy-memory/20260609T003851Z/*.html` atoms | 4 `.html` files | Pre-Markdown-migration; FROZEN, record-only |

---

## 8. Spec consistency

- **0 errors / 20 warnings** from `dadaia specs doctor` (context `dd-chain-explorer`).
- Status tokens: all live artifacts canonical (`Aprovado`). One archived, FROZEN exception (SDD-09).
- Phase consistency: `ACTIVE.md` says IMPLEMENTATION while TASKS is 16/16 `[x]` — the phase
  should have advanced to CLOSURE (SDD-01).
- No live PLAN/TASKS outside `releases/`; no closed release left outside `_archive/`; no SPEC
  outside `_archive/` treats an archived release as its authority. **All three clean.**
- `specs/assets/` is empty and no memory atom references an image — no broken image refs.
- Mermaid blocks parse structurally; several are semantically dead (SDD-12).
- Orphaned tasks: none in v0.4.0. `v0.3.0`'s A3/B2/B3 markers were left `[ ]`/`[-]` with an
  explicit `DEFERRED-TO-OPERATOR (2026-06-11)` annotation and deferral authority recorded in
  its CLOSURE — that is compliant, not orphaned, but those 8 operator items are still pending.
- Traceability: every v0.4.0 SPEC requirement maps into PLAN and at least one TASKS row.
  Conversely, **no v0.4.0 TASKS row cites a `20260611` audit finding id** — consistent with
  v0.4.0 not being that audit's remediation release, and consistent with SDD-23.

---

## 9. Compliance scorecard

Scored **for the SDD-drift lane only**. Dimensions D and E are lane-limited proxies —
`security-reviewer` and `qa-engineer` own the authoritative scores; do not merge these
numbers into theirs without reconciliation.

| Dimension | Score (1-10) | Drift items | One-line rationale |
|---|---|---|---|
| Architecture | **3** | SDD-02, SDD-05, SDD-12 | `architecture.md` still declares a 4-layer system whose first layer was deleted; 3 of 6 ADRs describe a superseded event bus and no superseding ADR exists |
| Product | **3** | SDD-12, SDD-13, SDD-14, SDD-15 | The rank-1/rank-2 catalog features document destroyed infrastructure; the two catalog indices disagree with each other; no atom describes the platform as it is today |
| Tech stack | **5** | SDD-12, SDD-16, SDD-17, SDD-26 | Python/Databricks/Terraform/CI/OIDC sections verified accurate; the AWS-infrastructure and module-inventory sections name two deleted modules and five destroyed services |
| Security | **4** | SDD-05, SDD-23, SDD-27 | Dead IAM grants for destroyed services persist, the 2026-06-11 security findings carry no disposition, and the one open bug is misfiled — SDD-lane proxy only |
| Tests | **4** | SDD-16, SDD-29 | 78 real tests exist but CI wires only the utils suite (WS-F5 open since June) and the streaming suite now guards an undeployed surface — SDD-lane proxy only |
| Agent-surface | **3** | SDD-01, SDD-18, SDD-20, SDD-21, SDD-23, SDD-24 | 0 doctor errors but 20 warnings, no `BACKLOG.md`, a stub constitution, two undispositioned audits, a done-but-open release, and an off-canon branch model |
| **Overall** | **3.7** | **29** | weighted 3.65, floor 3 → cap 5 → **final 3.7** |

Aggregation per `dd-audit-project`:
`weighted = 3(0.20) + 3(0.25) + 5(0.15) + 4(0.20) + 4(0.15) + 3(0.05) = 3.65`
`floor = min(3,3,5,4,4,3) = 3` → `cap = floor + 2 = 5` → `final = min(3.65, 5) = 3.7`

**Recommendation band:** `final < 5` → significant drift → recommend a dedicated remediation
release. No dimension is below 3, so there is no floor-breach escalation beyond the cap.
`project-auditor` recommends; `project-manager` opens; the operator decides.

---

## 10. Recommended actions (severity-ordered; each names its owner)

1. **Close v0.4.0 properly** — `product-engineer` writes the memory updates (§2, **including
   `architecture.md`**, which SPEC §8 omits), then `CLOSURE.md` with honest `## Validations`
   (SDD-07), a `## Drifts` entry for the mechanism substitution (SDD-08), and a `## Dispositions`
   sweep. Then `project-manager`/operator: ff-merge to `develop` → diff-based
   `security-reviewer` verdict → push → archive → free `ACTIVE.md`. *(SDD-01, SDD-12)*
2. **Close the capture-retirement regression vector** — `software-engineer` purges the HML
   capture provisioning/teardown lane from `deploy_all_dm_applications.yml` and
   `hml_provision.sh`. Until this lands, one app-deploy dispatch either fails on a deleted
   module or re-provisions destroyed infrastructure. *(SDD-03)*
3. **Disposition the 2026-06-11 audit** — `project-manager` compiles the operator intake
   report; the operator picks; **one** remediation release gives all 70 findings a terminal
   token. Archive `20260609T013037Z` immediately (fully dispositioned) after
   `dadaia specs doctor --fix` creates `specs/audits/_archive/`. *(SDD-23)*
4. **Re-file the misfiled bug** — `ai-engineer` registers
   `sdd-artifact-linter-mutates-task-markers` under `repos/dadaia-workspace/specs/bugs/`;
   the dd-chain-explorer entry is dispositioned with a pointer. This unblocks a clean v0.4.0
   Dispositions sweep. *(SDD-27)*
5. **Close the IaC residues** — `software-engineer`, under a `security-reviewer` verdict for
   the IAM half: dead 07_ecs symbols + `kinesis_sqs` alias (SDD-02), DEV `stack_map.json`
   modules arrays (SDD-04), capture IAM grants in `prd`/`hml` 03_iam (SDD-05), and the
   dev-compose/Makefile/dlt-test residues (SDD-06). Coordinate SDD-05 with the security lane.
6. **Fold the backlog** — `project-manager` builds `BACKLOG.md` (ACTIVE + LEDGER) from the §3
   inventory, ledgers the fully-done and capture-obsoleted items with reasons, and collapses
   the GAP-LD-2..6 duplication. Nothing is deleted. *(SDD-20, SDD-21, SDD-22)*
7. **Settle the branch model** — operator decision on `master`-vs-`main` and the default branch,
   then `software-engineer` lands `drift_detection.yml` + `plan_on_pr.yml` on whatever becomes
   the default so the Monday 06:00 UTC scan can fire for the first time. *(SDD-24, recap #8)*
8. **Decide the constitution** — operator: either `product-engineer` authors a real
   `specs/constitution.md` (the archived 231-line version is a starting point) or the operator
   explicitly ratifies its absence. Audits currently have no product-law anchor. *(SDD-18)*
9. **Clean the working tree** — `software-engineer` removes the 17 cache/state dirs and the
   duplicate test tree, and redirects the tools that create them. *(SDD-29)*
10. **Record-only, no action** — SDD-09, SDD-10, SDD-11, SDD-28 (FROZEN-path or cosmetic);
    SDD-19 routes upstream to `ai-engineer`/dadaia-workspace and never enters this repo's intake.

**Intake routing (FR6/R4).** Actionable → PM intake report: SDD-01..08, SDD-12..18, SDD-20..27,
SDD-29. Record-only, terminating here: SDD-09, SDD-10, SDD-11, SDD-19, SDD-28.

---

## 11. Evidence sources

- `dadaia context show --json`; `DADAIA_CONTEXT=dd-chain-explorer dadaia specs doctor`
  (0 errors / 20 warnings)
- `specs/releases/{ACTIVE.md, v0.4.0/{SPEC,PLAN,TASKS}.md}`; `specs/_archive/releases/**` (8 releases)
- All 11 memory atoms + `specs/memory/product/catalog.json`; `specs/memory/AGENTS.md`;
  `specs/constitution.md`
- `specs/backlog/**` (7 files); `specs/bugs/bugs.jsonl` + `_archive/archive.jsonl`
- `specs/audits/20260609T013037Z/audit.md`;
  `specs/audits/20260611T001412Z-cb56f84c/{consolidated-audit,architecture-review,security-review,cicd-terraform-review,sdd-drift-audit}.md`
- `.dadaia/handoff/dd-chain-explorer/2026-08-19T002955Z-project-auditor-full-recap-audit.handoff.json`
  (25 handoffs in the dir; this one read in full)
- Code: `services/{dev,hml,prd,modules}/**`, `apps/{docker,dabs,lambda}/**`,
  `.github/workflows/**` (7), `scripts/**` + `scripts/ci/**`, `Makefile`, `VERSION`
- Git: `git branch -vv`, `git branch -r`, `git log`, `git rev-list --left-right --count`,
  `git ls-tree origin/{master,develop}`, `git show --name-status c6feb17`

**Not covered by this lane** (owned by the parallel lanes, never asserted here as verified):
live AWS inventory and state, Databricks runtime, CI run history, the authoritative security
scan, and test-pyramid verdicts.

**No sub-agent was dispatched** (nested dispatch unavailable). Escalation trigger 2 of the
`project-auditor` protocol is therefore noted rather than blocking: the operator commissioned
this as one lane of a parallel sweep, and the fallback (direct evidence collection) was
available and used.
