# SDD Drift + Compliance Audit — dd-chain-explorer

- **Auditor:** project-auditor
- **Date (UTC):** 2026-06-11T00:14:12Z
- **Target:** `repos/dd-chain-explorer`, branch `feature/specs-first-docs-cleanup` (HEAD `34686a7`, working tree clean)
- **Trigger:** operator-requested post-onboarding follow-up audit (prior audit: `specs/audits/20260609T013037Z/audit.md`, score 6.2/10)
- **Method:** direct evidence gathering (Read/Grep/Bash) — no sub-agent dispatch (nested dispatch unavailable in this run). Two pre-existing specialist evidence reports in this audit dir were consumed (see Evidence sources).

---

## Executive Summary

The repo has substantially adopted the dadaia-workspace SDD pattern — active release with Aprovado artifacts, populated memory atoms with a generated `catalog.json`, archived legacy releases with evidence-bearing CLOSUREs, and 12/15 remediation tasks landed — but `dadaia specs doctor` now FAILS with **8 errors** (every bug file missing `session_id:` frontmatter), **7 of 8 bugs are fixed in code yet still `status: Open`**, and memory documents a Lambda-architecture data path (`b_ethereum.popular_contracts_txs` + `transactions_lambda` union, ADR-005) that **does not exist in code**. Consolidated score: **5.8/10** — moderate drift; the numeric drop vs the 6.2 prior audit reflects *new evidence surfaces* (a deep security review with 2 HIGH findings and a CI/Terraform review with 3 CRITICAL findings), not regression: every dimension the remediation release targeted genuinely improved.

---

## Scope

**Audited:**
1. SDD structure compliance — `dadaia specs doctor` (run as `DADAIA_CONTEXT=dd-chain-explorer` from workspace root), `releases/ACTIVE.md`, status tokens, memory frontmatter, `catalog.json` freshness, `_archive/` hygiene.
2. Memory vs code drift — all 8 atoms under `specs/memory/` (incl. `product/`) verified against `apps/`, `services/`, `utils/`, `.github/`, `Makefile`, `scripts/`.
3. `specs/domains/` canonicity vs the source-of-truth tree at `repos/dadaia-workspace/specs/`.
4. Bug (`specs/bugs/`, 8 files) and backlog (`specs/backlog/`, 5 files) hygiene.
5. Dead/stale code inventory + working-tree hygiene (`.hypothesis/`, `.databricks/`, `__pycache__`, build artifacts).
6. 6-dimension compliance scorecard per the drift-detection rubric.

**Excluded / unverifiable:** live AWS account state (resource existence, IAM as-applied), live Databricks workspace state (dashboard IDs, row counts, pipeline PAUSED status), SSM contents (e.g. the "17 Infura API keys" claim), dependency CVE scan (not run — see security evidence report). These memory claims are marked UNVERIFIABLE, not DRIFTED.

---

## Compliance Scorecard

| Dimension       | Score (1-10) | Drift items | Notes |
|-----------------|-------------|-------------|-------|
| Architecture    | 6 | 3 | Layer map and module boundaries confirmed against code; ADR-005 not implemented (stale); dangling Lambda-batch branch; HML↔PRD Terraform structural divergence (evidence: cicd review H5/H7/H2) |
| Product         | 6 | 4 | ~90% of memory claims verified exact (capture DAG, 15 gold MV names, replicas, compose topology); but `popular_contracts_txs` + `transactions_lambda` union documented-yet-absent; capture-supersession initiative unmentioned; QA atom is a stub |
| Tech stack      | 8 | 3 | 7 workflows, 16 CI scripts, 9 utils modules, pins, `python:3.12-slim`, 12 DEV containers all confirmed; minor: `eth-abi` floor stale, `dm-chain-utils` pin-policy mismatch (CI `==` vs memory `>=`), "60+ Make targets" vs 58 |
| Security        | 4 | 12 | Evidence: security-review.md — 0 CRITICAL but **2 HIGH open** (raw Infura key logged → durable log lakehouse; static AWS keys incl. PR-triggered plan) + 5 MEDIUM; no committed secrets; strong S3/IAM IaC baseline |
| Tests           | 5 | 3 | 71 new streaming-job unit tests (T-R5-D2) + 35 utils tests exist; **CI runs only the utils tests** (`deploy_all_dm_applications.yml:154`); DLT pipelines, Lambdas, dabs batch jobs: zero tests; no coverage measurement |
| Agent-surface   | 6 | 4 | `specs/AGENTS.md`, `memory/AGENTS.md`, `catalog.json` all landed (WS-A done); but doctor = 8 ERRORS (TREE-7 session_id on all bugs), 7 stale-Open bugs, audit-dir naming (SPEC-DOC-030), domains/ migration pending (T-R5-F1 open) |
| **Overall**     | **5.8** | **29** | weighted = A·.20 + B·.25 + C·.15 + D·.20 + E·.15 + F·.05 = 5.75; floor = min(...) = 4 → cap floor+2 = 6 → final = min(5.75, 6) = **5.8** |

Recommendation band (drift-detection policy): **5 ≤ 5.8 < 6 → moderate drift — dedicated tech-debt/hardening release via `project-manager`.** Security dimension = 4 is above the mandatory-escalation floor (<3) but is the binding constraint on the overall score.

### Scoring nuance vs prior audit (6.2 → 5.8)

This is **not a regression**. The 2026-06-09 remediation landed: SDD scaffold (was missing → present), streaming tests (0 → 71), logger fix, repo-boundary cleanup, release-closure forensics. The drop is driven by **net-new evidence** unavailable to the prior audit: the WS-E-follow-on deep security review (2 HIGH, incl. a full-key log leak the earlier streaming review missed) and the CI/Terraform code review (3 CRITICAL pipeline-gating defects). The prior audit's Tests=4 floor would also have been hit harder under today's doctor, which now errors (TREE-7) where it previously only warned.

---

## Drift inventory

Status legend: every claim checked is CONFIRMED, DRIFTED, or UNVERIFIABLE. Only DRIFTED items are listed; a sample of materially CONFIRMED claims follows the table.

| ID | Dim | Severity | Claim (memory) | Actual (code) | Evidence |
|----|-----|----------|----------------|----------------|----------|
| DRIFT-N01 | B/A | **HIGH** | Bronze table `b_ethereum.popular_contracts_txs` exists (STREAMING_TABLE from `raw/batch/`) | **No definition anywhere.** DLT pipeline defines only 3 bronze tables; no DDL in job_ddl_setup | `specs/memory/product/data-catalog.md:68`, `medallion-pipelines.md:40`, `architecture.md:114` vs `apps/dabs/dlt_ethereum/src/streaming/ethereum_pipeline.py` (24 `@dlt.table` — names enumerated, no `popular_contracts_txs`); `grep -rn popular_contracts_txs apps/dabs/job_ddl_setup/src/dd_chain_explorer/ddl/` → no DDL hit |
| DRIFT-N02 | B/A | **HIGH** | ADR-005 / `g_apps.transactions_lambda` = Lambda-architecture **union** of streaming ∪ batch (`popular_contracts_txs`), dedup by `tx_hash` with decode-quality priority full(1)…unknown(5) | Implementation is **streaming-only**: joins `s_apps.transactions_ethereum` with `g_apps.popular_contracts_ranking`; its own docstring says "(streaming only)". No union, no priority dedup | `specs/memory/architecture.md:232-234` (ADR-005), `data-catalog.md:113` vs `apps/dabs/dlt_ethereum/src/streaming/ethereum_pipeline.py:736-775` |
| DRIFT-N03 | B | **HIGH** (consequence of N01/N02) | `contracts_ingestion` Lambda feeds Bronze: "Lambda batch enrichment … delivers batch contract data to S3 `raw/batch/` → Bronze `popular_contracts_txs`" | Lambda writes JSON to `raw/batch/` hourly (EventBridge), but **nothing ingests it** — dangling producer. Its own docstring claims "DDL in job_ddl_setup" which does not exist | `medallion-pipelines.md:71` vs `apps/lambda/contracts_ingestion/handler.py:123` (false docstring) + absence of any consumer |
| DRIFT-N04 | B | MEDIUM | data-catalog totals: "30 objects: 12 streaming tables and 18 MVs" | Code defines **29** (`ethereum_pipeline.py`: 24; `dlt_app_logs`: 5). The missing object is `popular_contracts_txs` | `data-catalog.md:25,156-167` vs `@dlt.table` counts in both pipelines |
| DRIFT-N05 | B | MEDIUM | Memory presents the AWS ECS capture layer as unqualified current-and-future truth; `index.md` "Limites conhecidos" is silent on supersession | An **Aprovado** SPEC (capture-decoupling-r5, archived) migrates the capture layer to the sibling `dd-chain-capture` repo (VPS + Kafka + Redis; S3 boundary frozen); implementation exists in that repo, cutover pending | `specs/memory/product/index.md:53-60`, `capture-layer.md` (no mention) vs `specs/_archive/releases/capture-decoupling-r5/SPEC.md:1-30` |
| DRIFT-N06 | B/E | MEDIUM | `quality-assurance.md` should document QA standards/test discipline | Atom is a placeholder stub: "Padrões de qualidade ainda não documentados", `token_estimate: 0`, `last_updated: 2026-01-01` — stale even though the active release added 71 tests and reviewer gates | `specs/memory/quality-assurance.md:12-19` |
| DRIFT-N07 | C | MEDIUM | `dm-chain-utils >= 0.2.9` (range contract) | CI guard hard-pins `REQUIRED="dm-chain-utils==0.2.9"` — every utils bump silently breaks the gate | `specs/memory/tech-stack.md:44` vs `.github/workflows/deploy_all_dm_applications.yml:87` (evidence: cicd-terraform-review.md M6) |
| DRIFT-N08 | E | MEDIUM | (implicit in QA discipline / release evidence) streaming tests are the release's headline deliverable | The 71 new tests under `apps/docker/onchain-stream-txs/tests/unit/` are **not wired into any CI workflow** — CI runs only `utils/tests/unit/` | `.github/workflows/deploy_all_dm_applications.yml:154` (`pytest ${{ env.UTILS_DIR }}/tests/unit/`) vs `apps/docker/onchain-stream-txs/tests/unit/` (6 files, 71 `def test_`) |
| DRIFT-N09 | C | LOW | `eth-abi >= 2.0.0` | `eth-abi>=4.0.0` in requirements | `tech-stack.md:41` vs `apps/docker/onchain-stream-txs/requirements.txt:10` |
| DRIFT-N10 | C | LOW | "`make` — 60+ targets" | ~58 target rules counted | `tech-stack.md:189` vs `grep -cE '^[a-zA-Z0-9_.-]+:' Makefile` = 58 |
| DRIFT-N11 | F | LOW | Memory atom frontmatter `token_estimate` accurate | 6 atoms drift 25–50% from computed (doctor LINT-1); tracked by open task T-R5-F2 | doctor output; `specs/releases/audit-remediation-r5/TASKS.md:250` |
| DRIFT-N12 | A | INFO | `eth_canonical_blocks_index` "located at ethereum_pipeline.py:491–573" | Constant `_CANONICAL_WINDOW_BLOCKS = 1_000` at line 494; logic block offset a few lines — cosmetically stale line range | `architecture.md:128` vs `ethereum_pipeline.py:494` |

**Materially CONFIRMED claims (sample, all verified against code):** 5 streaming jobs with exact class/queue/stream names (`src/1..5_*.py`); job replicas 6/3 and 12 DEV containers (`services/dev/00_compose/app_services.yml:21-61`); all 15 gold MV names in `g_apps`/`g_network` match memory exactly; `dm-app-logs` 1+2+2; bounded-window refactor present; `warehouse_id a2a66f2adb0faf18` in 7 dabs YMLs; 7 GitHub workflows; 16 `scripts/ci/` scripts; 9 `dm_chain_utils` modules exactly as tabled; `VERSION`=0.2.9=`utils/pyproject.toml`=requirements pin; `FROM python:3.12-slim`; Terraform module inventory (9 modules) matches; BP-01 logger fix landed (class methods use `self.logger`; module-global `LOGGER` confined to `__main__` blocks in all 5 jobs).

**UNVERIFIABLE (no live access):** 17 Infura keys (SSM); dashboard ACTIVE statuses + DEV IDs; DLT trigger PAUSED state; DEV-validated row counts in data-catalog; account 016098071081 resource existence.

---

## Dead / stale code

| Item | Class | Evidence | Note |
|---|---|---|---|
| `contracts_ingestion` Lambda batch path (Lambda + EventBridge hourly + `raw/batch/` S3 prefix) | **Dangling producer** | `apps/lambda/contracts_ingestion/handler.py`; no Bronze consumer (DRIFT-N01/N03) | Produces data nothing ingests; either restore the `popular_contracts_txs` bronze + union (ADR-005) or retire the path and update memory |
| AWS capture stack (`apps/docker/onchain-stream-txs/`, `services/*/04_peripherals` SQS/Kinesis/Firehose, `07_ecs`) | **Supersession pending** | `_archive/releases/capture-decoupling-r5/SPEC.md` (Aprovado); sibling repo `dd-chain-capture` implements the replacement | NOT dead yet — cutover incomplete; flag only. Memory must cross-reference (DRIFT-N05) |
| `apps/docker/onchain-stream-txs/test/test_server.py` | Legacy orphan test (git-tracked) | only file in `test/` (singular); superseded by `tests/unit/` (71 tests); flagged as non-covering in `specs/bugs/drift-01-*.md` | Delete or fold into `tests/` |
| `apps/docker/onchain-stream-txs/src/configs/`, `src/schemas/` | Empty residue dirs (disk-only) | both dirs exist and are empty — drift-04 files were removed but the dirs remain (git cannot track empty dirs) | `rmdir` |
| `Makefile:327-330` `deploy_dev_all` | Broken target | references non-existent `services/compose/` (real path `services/dev/00_compose/app_services.yml`) | cicd review L1 |
| `Makefile:394` `prod_destroy_infra` | Broken target | calls undefined `tf_destroy_free_resources` | cicd review L2 |
| `Makefile:315-318,328,330` | Commented-out command corpses | `publish_apps` pushes only one image, rest commented | cicd review M11 |
| `apps/dabs/src/batch/**/{*.egg-info,dist}/`, `apps/dabs/job_ddl_setup/src/{build/lib,*.egg-info}/` | Build artifacts on disk (untracked) | `find apps/dabs/src -type f` → egg-info + wheels | clean working tree |

### Working-tree hygiene violations (all untracked/gitignored — `git ls-files` = 0 hits; still forbidden in-tree per workspace repo-cleanliness law)

- `.hypothesis/` at repo root (explicitly forbidden dir class).
- 13× `apps/dabs/<component>/.databricks/` bundle state dirs.
- 4× `__pycache__/` with `.pyc` (incl. stale `pytest-9.0.2/9.0.3` cache pairs).
- `services/prd/03_iam/.terraform/` + `.terraform.lock.hcl`, `services/prd/04_peripherals/.terraform/` (cicd review L6 — flip side: lockfiles gitignored ⇒ provider versions not reproducible in CI).

---

## Spec consistency

### Doctor result

`DADAIA_CONTEXT=dd-chain-explorer dadaia specs doctor` → **[fail] 8 error(s), 18 warning(s)**.

- **8 × ERROR TREE-7:** every file in `specs/bugs/` lacks the required `session_id:` frontmatter field (fix: add `session_id: null` — never fabricate an ID).
- **8 × WARN SPEC-DOC-007:** legacy SPEC/PLAN/TASKS under `specs/domains/` (see below).
- **1 × WARN LINT-1:** memory atom lint — token_estimate drift on 6 atoms + non-allowlist headings on 5 atoms (open tasks T-R5-F2/F3).
- **6 × WARN SPEC-DOC-027:** non-semver release dir names — `releases/audit-remediation-r5`, `releases/legacy`, and 4 archived legacy releases (preserved-until-renamed; acceptable for archives, the *active* release name is the actionable one going forward).
- **2 × WARN SPEC-DOC-030:** both audit dirs (incl. this one) lack the `-<session_id_8chars>` collision-safe suffix.

### Release state

- `ACTIVE.md`: `release: audit-remediation-r5 / phase: IMPLEMENTATION` — valid, points at an existing dir. SPEC/PLAN/TASKS all `**Status:** Aprovado` (canonical tokens). 12/15 tasks `[x]`, 3 open `[ ]` (T-R5-F1/F2/F3 — all WS-F LOW, consistent with PLAN's "WS-F may slip past rc-1"). No `[-]` reservations dangling. No orphaned tasks; every task maps to a SPEC workstream.
- `_archive/releases/`: 5 releases, each with `CLOSURE.md` `**Status:** Aprovado` and validation/drift/memory-update sections — closure hygiene (old drift-05) is resolved.
- **Non-canonical residue:** `specs/releases/legacy/SPEC.md` uses status token `Implementado` (not in `Draft|Em revisão|Aprovado`) and lives under live `releases/` rather than `_archive/` — should be archived with the other legacy artifacts.

### specs/domains/ — NOT canonical

The canonical pattern (source-of-truth: `repos/dadaia-workspace/specs/`) contains exactly: `AGENTS.md, constitution.md, _archive/, audits/, backlog/, bugs/, memory/, releases/`. **There is no `domains/` concept.** The 8 files under `specs/domains/{applications,data-analytics,data-engineering,devops,infrastructure}` (+ `applications/rest-api/`) are pre-onboarding legacy, carry non-canonical status tokens (`Implementado`, `Not started`, `Not implemented — spec written 2026-04`), and are correctly flagged by doctor as SPEC-DOC-007. Migration/archival is already scoped as open task **T-R5-F1**. Until then they are a standing source of false authority — nothing should treat them as approval.

### Memory catalog freshness

`specs/memory/product/catalog.json` (generated 2026-06-09T02:02:49Z, T-R5-A2) is **consistent with atom frontmatter**: 5 features, slugs/titles/tldr/tags/token_estimates match, all `path` values resolve, `index.md` links all 5 atoms. (The token_estimates faithfully mirror frontmatter — which itself drifts from computed size, LINT-1/T-R5-F2.)

---

## Bug / backlog hygiene

### Bugs (8 files) — primary issue: stale `Open` statuses + missing session_id

| Bug | status field | Fixed in code? | Verdict |
|---|---|---|---|
| `bp-01-streaming-jobs-logger-inconsistency` | Open | **YES** — commit `c789e9c`; all 5 job classes now use `self.logger` in methods (verified jobs 1–5) | **STALE-OPEN** |
| `drift-01-streaming-jobs-zero-tests` | Open | **YES** — commit `226740e`; 71 tests in `tests/unit/` | **STALE-OPEN** |
| `drift-02-dadaia-dir-inside-repo` | Open | **YES** — no `.dadaia/` in repo (disk + `git ls-files` clean) | **STALE-OPEN** |
| `drift-03-specs-bkp-migration-leftover` | Open | **YES** — `specs_bkp/` gone | **STALE-OPEN** |
| `drift-04-kafka-avro-dead-code` | Open | **YES (substantively)** — all 7 avro schemas + 3 kafka configs removed; only empty `configs/`+`schemas/` dirs remain on disk; remaining kafka mentions are migration comments | **STALE-OPEN** (close after `rmdir`) |
| `drift-05-release-closure-hygiene` | Open | **YES** — the 3 releases forensically closed + archived with Aprovado CLOSUREs (T-R5-C1..C3) | **STALE-OPEN** |
| `drift-06-08-sdd-structure-gaps` | Open | **YES** — `specs/AGENTS.md`, `specs/memory/AGENTS.md`, `catalog.json` all exist | **STALE-OPEN** |
| `drift-10-doctor-warnings-batch` | Open | Partially — domains/ + token_estimate + headings still open (T-R5-F1/F2/F3) | Correctly Open |

All 8 carry `name/status/severity/reported/surface` frontmatter ✓ but **none carries `session_id:`** → the 8 doctor ERRORs. Closing flow note: bug closure normally lands with release CLOSURE — but the release is in IMPLEMENTATION with all corresponding tasks `[x]`; statuses should be reconciled (Fixed/Closed + `fixed_in:` ref) at or before CLOSURE so the registry stops contradicting the tree.

### Backlog (5 files) — healthy

- `remediation-audit-20260609.md` — picked set, maps 1:1 to bugs, bug-always-solved table ✓.
- `rebuild-abandoned-r2-r3-r4-capabilities.md` — CANDIDATE epic, explicitly not picked, evidence-sourced from CLOSURE forensics ✓.
- `streaming-jobs-security-hardening.md` — CANDIDATE, deferred LOW/INFO security findings, traceable to WS-E handoff ✓. **Note:** security-review.md (this audit dir) adds net-new H-01/H-02/M-01..M-05 *beyond* this backlog item — it does not cover them.
- `candidates.md` / `ideas.md` — curated, resolved-questions record kept ✓.

No stale or contradictory backlog entries found.

---

## Recommended actions (severity-ordered; remediation dispatch is project-manager's)

1. **HIGH (security):** Triage the two HIGH findings in `security-review.md` — H-01 raw Infura key logged at `4_mined_txs_crawler.py:66,107,114` (durable propagation to the log lakehouse; rotate exposed keys) and H-02 static AWS keys across all 7 workflows incl. PR-triggered plan. → `project-manager` to scope into the next release (extends the existing `streaming-jobs-security-hardening` candidate); fix by `software-engineer`; operator decisions OI-A..OI-E listed in that report.
2. **HIGH (product/architecture):** Resolve the ADR-005 / `popular_contracts_txs` / `transactions_lambda` contradiction (DRIFT-N01..N04): either implement the documented union path or retire the dangling `contracts_ingestion` batch branch and rewrite ADR-005 + data-catalog + medallion-pipelines atoms to the streaming-only reality. Decision: `software-architect` evidence + operator; memory rewrite by `product-engineer` (DEFINITION/CLOSURE phase).
3. **HIGH (CI integrity):** The 3 CRITICALs in `cicd-terraform-review.md` (blind auto-approved PRD apply; `tail -1` cross-stack apply gating; unguarded destroy-all concurrency). → `project-manager`; CI YAML is plugin-domain (`devops-engineer` — devops plugin) or operator-approved `software-engineer` scope.
4. **MEDIUM (structure, cheap):** Add `session_id: null` to all 8 bug files (clears all 8 doctor ERRORs) and reconcile the 7 STALE-OPEN bug statuses with `fixed_in:` commit refs. → `project-manager`/`product-engineer` (bugs are ADDITIVE).
5. **MEDIUM (tests):** Wire `apps/docker/onchain-stream-txs/tests/unit/` into CI next to the utils test step (`deploy_all_dm_applications.yml:154`); fix the `dm-chain-utils` `==` vs `>=` pin-policy mismatch (M6). → `software-engineer` + `qa-engineer`.
6. **MEDIUM (memory):** Populate `quality-assurance.md` (stub); add the capture-supersession cross-reference (dd-chain-capture) to `index.md`/`capture-layer.md`; fix `eth-abi` floor. → `product-engineer` at CLOSURE.
7. **LOW (already-tracked):** Finish T-R5-F1 (archive `specs/domains/` + `releases/legacy/`), T-R5-F2 (token_estimates), T-R5-F3 (heading allowlist); delete dead Makefile targets (L1/L2/M11) and `test/test_server.py`; `rmdir` empty `configs/`/`schemas/`; clean `.hypothesis/`, `.databricks/`, `__pycache__`, `.terraform/`, dabs build artifacts from the working tree.
8. **LOW (naming, forward-only):** Use semver release ids and `<ts>-<session8>` audit dir names going forward (SPEC-DOC-027/030).

---

## Evidence sources

| Source | Type |
|---|---|
| `dadaia specs doctor` run (2026-06-11, `DADAIA_CONTEXT=dd-chain-explorer`) | tool output — 8 ERR / 18 WARN |
| `specs/audits/20260611T001412Z/security-review.md` | security-reviewer evidence report (pre-existing in this audit dir) — 0 CRIT / 2 HIGH / 5 MED / 5 LOW / 3 INFO |
| `specs/audits/20260611T001412Z/cicd-terraform-review.md` | code-reviewer evidence report (pre-existing) — 3 CRIT / 8 HIGH / 11 MED / 7 LOW, REQUEST_CHANGES |
| `specs/audits/20260609T013037Z/audit.md` | prior project-auditor baseline (6.2/10) |
| Direct file:line verification | this audit — all citations inline above |
| `repos/dadaia-workspace/specs/` tree listing | canonical-pattern comparator for §specs/domains |

*No fixes were performed. This report is measurement only; remediation routing belongs to `project-manager`.*
