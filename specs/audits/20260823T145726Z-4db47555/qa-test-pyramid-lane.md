# QA Audit — Test Pyramid + Test Stewardship — dd-chain-explorer

**Repo:** `<repo>`
**Branch:** `feature/v0.4.0` (HEAD `c6feb17`, 1 commit ahead of `origin/feature/v0.4.0`, tree clean)
**Date:** 2026-08-23
**Auditor:** qa-engineer (audit-mode dispatch, read-only)
**Release context:** `specs/releases/ACTIVE.md` → `release: v0.4.0`, `phase: IMPLEMENTATION`. All TASKS.md items `[x]` except the operator-gated live-destroy (also `[x]`, done 2026-06-22). No CLOSURE.md yet — release is done-but-unmerged per prior memory.

---

## 0. Executive summary

The test suite that exists is **small, hermetic, and high quality** (158/158 passing,
sub-3s runtime, no flakes, no mocks-that-defeat-the-test found). The problem is not test
quality — it is **wiring and coverage breadth**: CI runs exactly one of three existing
pytest suites, two entire application layers (Lambda, DABs/DLT — ~3,800 LOC of production
code) have **zero** tests, Terraform has no test tooling at all, and — the most severe
finding — **the only CI workflow capable of deploying to PRD Lambda/DABs
(`deploy_all_dm_applications.yml`) was never updated for the v0.4.0 Capture Retirement**
and will now fail (or silently rubber-stamp) its own HML gate the next time anyone runs
it, because it still provisions/tests/destroys Kinesis/SQS resources whose Terraform
modules this same release deleted.

| # | Severity | Area | Finding |
|---|---|---|---|
| F1 | **CRITICAL** | CI/CD wiring | `deploy_all_dm_applications.yml` (the only PRD Lambda/DABs deploy path) still provisions ephemeral HML Kinesis/SQS/ECS-producer resources and destroys `module.kinesis` at teardown — both Terraform modules were deleted by this same release. Next `workflow_dispatch` run will hard-fail at `hml_provision.sh`'s `aws sqs get-queue-url` (queue no longer exists) or error at teardown's `terraform destroy -target=module.kinesis` (target no longer exists). |
| F2 | **HIGH** | CI/CD wiring | Even if F1 didn't hard-fail, the workflow's own gate is now a rubber stamp: `scripts/hml_integration_test_optimized.sh`, the script that decides `all-hml-test-streaming.outputs.test_passed` (which gates `all-check-infra` → PRD deploy), was correctly tombstoned to `echo …; exit 0` by T-D.5 — but the *workflow* still treats that unconditional pass as real validation. The DABs HML test (`all-hml-test-dabs`) also silently degrades: it expects `raw/` S3 data delivered by the now-destroyed HML Firehose. |
| F3 | MEDIUM | CI execution coverage | `scripts/ci/tests/` (45 tests covering `deploy_env.sh`'s apply-path safety, `plan_gate_check.sh`'s destroy-ack/divergence gates, and `stack_map.json` integrity — i.e. the tests for the CI/CD pipeline's own safety mechanisms) are **never run in CI**, and unlike the streaming-job gap this one is not tracked in any backlog item. |
| F4 | MEDIUM (tracked) | CI execution coverage | `apps/docker/onchain-stream-txs/tests/unit/` (78 tests) still never wired into CI. Already tracked as backlog item **F5** in `platform-audit-remediation-20260611.md` (WS-F) — confirmed still open, not stale. |
| F5 | MEDIUM | Test artifact hygiene | `apps/docker/onchain-stream-txs/test/test_server.py` (singular `test/`, sibling of the real `tests/unit/`) is a stray manual smoke script — no `test_*` functions, no assertions, a live-network `__main__` block. Orphan debris, not part of the suite (pytest won't even collect it under default discovery from `tests/`). |
| F6 | LOW | Coverage gap | 5 of 10 `dm_chain_utils` modules have **no dedicated test file**: `dm_dynamodb.py` (21%), `dm_etherscan.py` (22%), `dm_firehose.py` (22%), `dm_parameter_store.py` (15%), `api_keys_manager.py` (31%). `dm_dynamodb`/`dm_parameter_store`/`api_keys_manager` back live Lambda + DABs code paths. |
| F7 | LOW | Coverage gap | `apps/docker/onchain-stream-txs/src/utils_decode/abi_cache.py` (41 stmts) — 0% coverage, no test file, despite being on the hot path of job 5's decode logic and imported (but only mocked) by `test_5_txs_input_decoder.py`. |
| F8 | LOW | Test stewardship | None of the 158 tests use the formal `Intent: <KIND> — <AC id>` docstring line prescribed by `dadaia-test-stewardship` §A. All have good descriptive docstrings instead. By the letter of the rule they are undeclared → SCAFFOLD; in practice they read as durable CONTRACT/unit tests. Retrofit recommended, not urgent. |
| F9 | LOW | Documentation staleness | `scripts/dev_dlt_integration_test.sh` (not wired into any CI workflow; local/manual only) still documents "Data flowing from Firehose → S3 raw/ prefix" as a prerequisite — Firehose no longer exists in `dev` either, post-v0.4.0. |
| F10 | INFO | Terraform | No Terraform test tooling anywhere (`tfsec`/`checkov`/`terratest`/`terraform-compliance`) — only `terraform validate`/`fmt -check` (syntax, not policy/security). Out of this release's declared scope; flagged as a standing gap. |

Full evidence and recommendations follow.

---

## 1. Test inventory (by component)

| Component | Location | Kind | Files | Test fns | Runtime | Coverage (measured) |
|---|---|---|---|---|---|---|
| `dm-chain-utils` (shared lib) | `utils/tests/unit/` | unit | 4 | 35 | 2.72s | 42% stmt (699 stmts, `utils/src/dm_chain_utils`) |
| `onchain-stream-txs` (capture producer, source retained, ECS deploy retired) | `apps/docker/onchain-stream-txs/tests/unit/` | unit | 6 + conftest | 78 | 0.25–0.56s | 59% stmt (658 stmts, `apps/docker/onchain-stream-txs/src`) |
| `scripts/ci` (CI/CD pipeline logic) | `scripts/ci/tests/` | integration (hermetic, stub-binary subprocess) | 3 | 45 | 1.42s | not measured (bash-under-test, not importable Python) |
| `onchain-stream-txs` stray smoke script | `apps/docker/onchain-stream-txs/test/test_server.py` | none (not a real test) | 1 | 0 | — | — |
| `apps/lambda` (`contracts_ingestion`, `gold_to_dynamodb`) | — | **none exist** | 0 | 0 | — | 0% (392 LOC untested) |
| `apps/dabs` (DLT pipelines, jobs, dashboards, alerts, genie) | — | **none exist** | 0 | 0 | — | 0% (~3,800 LOC across `dlt_ethereum` 1,519 + `dlt_app_logs` 337 + `job_export_gold` 102 + `job_delta_maintenance` 460 + `job_ddl_setup` 868) |
| `services/` (Terraform, 93 `.tf` files) | — | **none exist** (no tfsec/checkov/terratest) | 0 | 0 | — | `terraform validate`/`fmt` only (syntax) |
| Shell integration tests (retired-tombstone) | `scripts/{hml_integration_test,hml_integration_test_optimized,dev_integration_test}.sh` | e2e (now no-op stubs, 20–27 lines each) | 3 | 0 (stub `exit 0`) | instant | n/a — asserts nothing |
| Shell integration tests (live, DLT) | `scripts/{dev,hml}_dlt_integration_test.sh` | e2e (real, Databricks/AWS-dependent) | 2 | n/a | not runnable locally (needs live Databricks workspace + AWS creds) | n/a |

**Total runnable, currently-green pytest tests: 158** (35 + 78 + 45). **Total repo-tracked test files (incl. the stray + tombstones): 17** Python/shell test artifacts.

No integration or E2E test tier exists in the pytest sense for this repo — the shell scripts are the E2E layer, and two of the three capture-related ones are now intentional no-ops (correctly tombstoned per SPEC v0.4.0 §3.2), while the two DLT ones are live-environment-dependent and were not exercised in this audit (no Databricks/AWS credentials used, per the read-only/no-mutation constraint).

---

## 2. Run results

Environment: throwaway venv at
`.dadaia/tmp/qa-engineer/20260823/venv` (system `python3.12`, isolated from the workspace
venv), `pytest -p no:cacheprovider`, `PYTHONDONTWRITEBYTECODE=1`,
`COVERAGE_FILE=.dadaia/tmp/qa-engineer/20260823/.coverage-<suite>`.

| Suite | Command | Result |
|---|---|---|
| `utils/tests/unit/` | `pytest utils/tests/unit/ -p no:cacheprovider --cov=utils/src/dm_chain_utils` | **35 passed**, 0 failed, 0 skipped, 0 xfail, 2.72s |
| `apps/docker/onchain-stream-txs/tests/unit/` | `pytest apps/docker/onchain-stream-txs/tests/unit/ -p no:cacheprovider --cov=apps/docker/onchain-stream-txs/src` | **78 passed**, 0 failed, 0 skipped, 0 xfail, 0.25–0.56s |
| `scripts/ci/tests/` | `pytest scripts/ci/tests/ -p no:cacheprovider` | **45 passed**, 0 failed, 0 skipped, 0 xfail, 1.42s |
| `apps/docker/onchain-stream-txs/test/test_server.py` | not a pytest target (no `test_*` functions) | not collected — 0 tests |
| DABs / Lambda / Terraform | no test files exist | nothing to run |
| `scripts/{dev,hml}_dlt_integration_test.sh` | requires live Databricks + AWS | **not runnable locally** — needs `DATABRICKS_HOST`/`DATABRICKS_TOKEN` and live AWS role assumption; not attempted (would mutate/query real infra, out of this audit's read-only scope) |

**158/158 pytest tests green.** No environment-vs-real-bug distinction needed — every
attempted suite ran clean with only ordinary dependency installs (`pip install -e
utils[dev]`, `pytest-cov`, `requests`, `aiohttp`, `eth-abi`) into the throwaway venv; no
product code changes or workarounds were needed to get to green.

---

## 3. Stewardship findings

| Check | Result |
|---|---|
| Undeclared intent (`Intent: <KIND> — <AC id>` per `dadaia-test-stewardship` §A) | **None of the 158 tests use this literal format.** All have substantive human-readable module/class docstrings describing what each test covers (e.g. `test_etherscan_multi.py` explicitly cites `F-02 (CWE-918 SSRF)`). By the letter of the rule, undeclared = SCAFFOLD; in substance these read as permanent CONTRACT-tier unit tests. See F8. |
| `pytest.mark.skip` / `xfail` / `quarantine` | **None found** anywhere in the tree (`grep -rniE 'skip|xfail'` across all three suites hits only test *names* like `test_run_skips_contract_deploys` and in-code business-logic "skip" semantics — no test-collection skip markers). |
| Sleep/time-based flake patterns | **None found.** The one `time.sleep` reference in `test_1_mined_blocks_watcher.py` is a comment describing that production `time.sleep` is *patched to no-op*, not a real sleep in the test. |
| Tests exercising removed capture functionality (Kinesis/SQS/Firehose/ECS producers) | `utils/tests/unit/test_kinesis.py` (8 tests) and `test_sqs.py` (11 tests) still test `dm_chain_utils.dm_kinesis.KinesisHandler` / `dm_sqs.SQSHandler` library code. **This is explicitly out of scope for v0.4.0** — SPEC OQ-5 resolved "dm-chain-utils Kinesis/SQS/Firehose handlers stay; cleanup is a separate backlog item (`dm-chain-utils-capture-handler-cleanup`)" — so these tests are correctly still testing live (if now-unused-by-this-repo) library surface, not a stewardship violation today. Revisit when that backlog item is picked. `apps/docker/onchain-stream-txs/tests/unit/*.py` test the 5 producer job *classes* whose ECS deployment was retired but whose source code is explicitly retained (SPEC §3 scope: Terraform/tooling only, not `apps/docker/**`) — same reasoning applies, not a violation. |
| Duplicate tests | None found within the 158 collected tests. The one duplicate-*shaped* artifact is F5 (`apps/docker/onchain-stream-txs/test/test_server.py` vs `tests/unit/`) — not a duplicate test, an orphan non-test file that only superficially resembles one by directory naming. |
| Tombstone tests (assert absence of removed capability) | The 3 gutted shell scripts (`hml_integration_test.sh`, `hml_integration_test_optimized.sh`, `dev_integration_test.sh`) are tombstones by the `dadaia-test-stewardship` definition — each now exists solely to declare "this capability is gone" and unconditionally `exit 0`. Per the tombstone ban, they were correctly born SCAFFOLD of the release that removed the capability and should be **deleted at v0.4.0 CLOSURE** (the removal event belongs in `CLOSURE.md`/changelog, not as a permanent no-op script). Not yet closed — this release has no `CLOSURE.md`. |
| Flake/quarantine registry | Quarantine cap N/A — 0 quarantined tests, cap (8, per this workspace's own default) not applicable to a consumer repo without the doctrine formally adopted; no flaky-history evidence found in `specs/bugs/bugs.jsonl` (17 lines, none test-flake related). |

---

## 4. Gaps

### 4.1 Production code with zero tests

| Path | LOC | Notes |
|---|---|---|
| `apps/lambda/contracts_ingestion/handler.py` | 309 | PRD lambda, S3-triggered contract ingestion; zero tests |
| `apps/lambda/gold_to_dynamodb/handler.py` | 83 | DEV lambda, S3 PutObject → DynamoDB export; zero tests |
| `apps/dabs/dlt_ethereum/src/streaming/ethereum_pipeline.py` | 1,519 | The core DLT medallion transform (4 bronze + 6 silver + 15 gold); zero tests, not runnable locally without a Spark/DLT harness (not attempted — would need `pyspark`+DLT decorators stubbed; flagged as a follow-up, not attempted here since the file has no existing test scaffold to run) |
| `apps/dabs/dlt_app_logs/src/streaming/app_logs_pipeline.py` | 337 | Same pattern, app-logs pipeline |
| `apps/dabs/job_export_gold/src/batch/dm_export_gold/export_gold.py` | 102 | Batch gold export; zero tests |
| `apps/dabs/job_delta_maintenance/src/batch/dm_delta_maintenance/{monitor,optimize_bronze,optimize_gold,optimize_silver,vacuum}.py` | 460 combined | Delta maintenance batch jobs; zero tests |
| `apps/dabs/job_ddl_setup/src/dd_chain_explorer/{check/check_tables,ddl/setup_ddl}.py` | 868 combined | DDL setup/check (imports `pyspark`); zero tests |
| `scripts/ci/*.sh` (14 non-test shell scripts, ~2,000 LOC) | — | Most CI orchestration logic (`deploy_env.sh`, `hml_provision.sh`, `destroy_env.sh`, etc.) has no direct test — only `deploy_env.sh`'s apply-path and `plan_gate_check.sh` are covered, via `scripts/ci/tests/` (§1) |

### 4.2 Terraform (`services/`, 93 `.tf` files)

No `tfsec`, `checkov`, `terratest`, or `terraform-compliance` anywhere in the repo or CI.
Only `terraform validate` (syntax/reference checks) and `terraform fmt -check` run in
`plan_on_pr.yml`/`deploy_cloud_infra.yml`. This is a standing gap outside v0.4.0's
declared scope — not a regression this release introduced.

### 4.3 CI test execution coverage — which suites actually run

Confirmed by exhaustive grep across every `.github/workflows/*.yml` and the `Makefile`
(no `test` targets exist in the Makefile at all):

```
.github/workflows/deploy_all_dm_applications.yml:163:  pytest ${{ env.UTILS_DIR }}/tests/unit/ -v --tb=short
```

This is the **only** `pytest` invocation in the entire CI configuration. `scripts/ci/tests/`
(45 tests) and `apps/docker/onchain-stream-txs/tests/unit/` (78 tests) — 123 of the 158
green tests found in this repo — never execute in CI. A regression in either suite is
invisible until a human runs it manually.

### 4.4 The CI/CD wiring break (F1/F2 — see §0)

`deploy_all_dm_applications.yml`'s HML deploy+test phase (lines ~235–786) was not touched
by v0.4.0's TASKS (T-D.5's write set was scoped to `scripts/*.sh` + `scripts/ci/hml_teardown.sh`
only — never the calling workflow YAML). Concretely, post this release's Terraform changes
(`services/modules/kinesis/` and `services/modules/sqs/` deleted; `hml/04_peripherals`
no longer declares `module "kinesis"`/`module "sqs"`, confirmed by
`grep -n 'module "kinesis"' services/hml/04_peripherals/main.tf` returning nothing):

- `all-hml-infra-apply`'s step "Apply HML peripherals (SQS + Kinesis + S3 + DynamoDB +
  CloudWatch)" (workflow line 257) is now a stale label but not itself broken — it just
  applies a peripherals stack that no longer declares those resources.
- `scripts/ci/hml_provision.sh` (called by `all-hml-provision`) does
  `aws sqs get-queue-url --queue-name "mainnet-mined-blocks-events-hml"` — **this queue no
  longer exists**; the call will fail and hard-fail the job (no HML deploy/test proceeds
  past this point on any real run).
- `all-hml-stream-launch` registers ECS task-defs with `KINESIS_STREAM_*`/`FIREHOSE_STREAM_*`
  env vars pointing at destroyed streams.
- `all-hml-test-streaming` invokes `scripts/hml_integration_test_optimized.sh`, which — per
  T-D.5's *own correct* work — is now `echo …; exit 0` (F2): even if the earlier steps were
  patched to not fail, this step would report `test_passed=true` unconditionally, defeating
  the `all-check-infra`/PRD-deploy gate's purpose.
- Teardown's "Destroy HML Kinesis streams" step (`terraform … destroy
  -target='module.kinesis'`, line ~785) targets an address Terraform will reject as
  invalid once the module is gone — mitigated only by that step's `continue-on-error: true`
  (line 786), so teardown itself won't fail the run, but it will emit a hard Terraform
  error in the log.

This workflow is `workflow_dispatch`-only (manual trigger) and is confirmed (per prior
session memory) to be the **only** path that deploys updated Lambda code or DABs bundles to
PRD. It has very likely not been re-run since the v0.4.0 Terraform changes landed (release
is "done but unmerged/no CLOSURE" per prior audit), so this break has not yet surfaced in a
real run — it is a live landmine for the next PRD Lambda/DABs deploy attempt, not yet an
observed production failure. Recorded here as a finding, not filed as a deploy-validation
FAIL (no live/staging run was executed in this audit).

---

## 5. Comparison with `specs/memory/quality-assurance.md`

| Atom claim | Reality | Verdict |
|---|---|---|
| "71 streaming-job unit tests" | 78 collected (6 job test files + `test_etherscan_multi.py`) | **Stale count** — grew by 7 since the atom's `last_updated: 2026-06-11`; not false, just drifted. |
| "35 utils unit tests" | 35 confirmed, all green | **Accurate.** |
| "CI runs **only** the utils suite... 71 streaming-job tests are not wired into any workflow — tracked as WS-F5" | Confirmed accurate — CI still runs only `utils/tests/unit/`; the backlog item is `WS-F` item `F5` in `platform-audit-remediation-20260611.md`, still present/open (not archived, not superseded) | **Accurate**, still open. |
| "DLT pipelines, Lambdas, and dabs batch jobs have zero tests" | Confirmed — 0 test files under `apps/lambda/` or `apps/dabs/` anywhere | **Accurate.** |
| "No coverage measurement is configured" | Confirmed — no `--cov` anywhere in CI or the two pytest invocations that exist locally; this audit added throwaway `--cov` runs outside the repo tree only | **Accurate.** |
| — (not mentioned at all) | `scripts/ci/tests/` (45 tests, CI/CD pipeline safety-mechanism tests) exists and is also never wired into CI | **Missing from the atom** — F3 is a genuine gap in the atom's own inventory, not just staleness. |
| — (not mentioned at all) | The `deploy_all_dm_applications.yml` HML wiring break (F1/F2) postdates the atom (`release_origin: audit-remediation-r5`, well before v0.4.0) | Not a contradiction — the atom predates this release's changes; flagged here as new information for the CLOSURE update. |
| Anti-slop discipline bullets (no fabricated tests/SHAs, `-p no:cacheprovider`, bug records close with evidence) | Confirmed still practiced — `scripts/ci/tests/` docstrings explicitly say "run with `-p no:cacheprovider`"; no fabricated evidence found in this audit | **Accurate**, still practiced. |

**Memory update recommendation (for `product-engineer` at v0.4.0 CLOSURE, not executed by
this agent):** rewrite `quality-assurance.md` to (a) correct the streaming-job count to
78, (b) add `scripts/ci/tests/` (45 tests) to the inventory table with the same "not wired
into CI" caveat, (c) record the tombstone-script deletion (§3) as part of this release's
disposition, and (d) flag F1/F2 for the operator/PM to route into an intake item.

---

## 6. Recommendation — minimal viable pyramid for the post-retirement platform

Target shape for the surviving S3 → DLT → serving architecture (capture now lives in
`dd-chain-capture`; S3 is the sole integration boundary):

**Priority 1 — stop the bleeding (wiring, not new tests):**
1. Fix or retire `deploy_all_dm_applications.yml`'s HML capture-provision/test/teardown
   phase (F1/F2) before the next PRD Lambda/DABs deploy is attempted. This is the single
   highest-leverage fix — it unblocks the only PRD deploy path and removes a false-green
   signal from the release gate.
2. Wire `scripts/ci/tests/` and `apps/docker/onchain-stream-txs/tests/unit/` into a CI
   job (e.g. extend the existing `all-lambda-build-artifacts` pattern, or add a
   dedicated `unit-tests` job gating `branch-guard`). Zero new tests required — just a
   `pytest` step, ~2s added runtime.
3. Delete the 3 tombstoned shell scripts (`hml_integration_test.sh`,
   `hml_integration_test_optimized.sh`, `dev_integration_test.sh`) and the stray
   `apps/docker/onchain-stream-txs/test/test_server.py` at v0.4.0 CLOSURE, per the
   tombstone ban and F5.

**Priority 2 — close the zero-coverage production gaps (small, targeted additions):**
4. `apps/lambda/*/handler.py` (392 LOC combined) — unit tests with mocked
   boto3/S3 events; this is the same hermetic pattern already proven in
   `utils/tests/unit/` and `onchain-stream-txs/tests/unit/`. Estimated: 15–25 tests.
5. `dm_chain_utils.dm_dynamodb` / `dm_parameter_store` / `api_keys_manager` (F6) — these
   back the Lambda + DABs code paths directly; same mocked-boto3 pattern as the existing
   `test_kinesis.py`/`test_sqs.py`. Estimated: 15–20 tests.
6. `apps/dabs/job_export_gold/export_gold.py` + `job_delta_maintenance/*.py` (562 LOC) —
   these are plain Python (no DLT decorators), testable with a local/mocked Spark session
   or pure-function extraction; lower effort than the DLT pipelines themselves.

**Priority 3 — the expensive layer (defer, do not over-invest):**
7. `dlt_ethereum_pipeline.py` / `dlt_app_logs_pipeline.py` (1,856 LOC) — true DLT/Spark
   unit testing requires either a local Spark harness or restructuring transform logic
   into plain-function units the DLT decorators wrap thinly (preferred: extract testable
   pure functions, keep DLT decorators as a thin adapter layer — avoids needing `pyspark`
   in CI at all for the bulk of the logic). Do not attempt full pyspark-in-CI unit testing
   without first doing this extraction — it is the expensive path for comparatively low
   marginal detection value versus extraction + pure-function tests.
8. Terraform policy/security scanning (`tfsec`/`checkov`) — standing gap, low urgency
   given `terraform validate` + the destroy-ack/plan-diff safety net already tested by
   `scripts/ci/tests/test_deploy_apply_path.py` provide meaningful protection today.

**What NOT to do:** do not add volume-padding tests to `apps/dabs`/`apps/lambda` just to
hit a percentage; the existing 158 tests are proof this team writes focused, hermetic,
fast tests — extend that pattern rather than importing a different (heavier, slower)
testing style for the new modules.

---

## Appendix — commands run

```bash
# throwaway venv, isolated from workspace venv
python3 -m venv .dadaia/tmp/qa-engineer/20260823/venv
.dadaia/tmp/qa-engineer/20260823/venv/bin/pip install -e "repos/dd-chain-explorer/utils[dev]" pytest-cov requests aiohttp eth-abi

cd repos/dd-chain-explorer
PYTHONDONTWRITEBYTECODE=1 COVERAGE_FILE=.../.coverage-utils \
  pytest utils/tests/unit/ -p no:cacheprovider -o cache_dir=.../pycache -v --cov=utils/src/dm_chain_utils --cov-report=term-missing
# → 35 passed, 42% coverage

PYTHONDONTWRITEBYTECODE=1 COVERAGE_FILE=.../.coverage-stream \
  pytest apps/docker/onchain-stream-txs/tests/unit/ -p no:cacheprovider -v --cov=apps/docker/onchain-stream-txs/src --cov-report=term-missing
# → 78 passed, 59% coverage

PYTHONDONTWRITEBYTECODE=1 pytest scripts/ci/tests/ -p no:cacheprovider -v
# → 45 passed

grep -rn 'pytest' .github/workflows/           # → 1 hit, utils/tests/unit/ only
grep -n 'module "kinesis"' services/hml/04_peripherals/main.tf   # → no match (confirms deletion)
grep -n 'module.kinesis\|get-queue-url' .github/workflows/deploy_all_dm_applications.yml scripts/ci/hml_provision.sh
```

No AWS/Databricks CLI calls were made. No repository files were modified. All coverage
data files and the throwaway venv live under
`.dadaia/tmp/qa-engineer/20260823/` (outside the repo tree).
