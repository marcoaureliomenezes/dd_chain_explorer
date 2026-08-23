# Re-audit after the v0.5.0 remediation release — dd-chain-explorer

> **Date:** 2026-08-23 (UTC stamp `20260823T182948Z`) · **Session:** 4db47555 · **Task:** `T-R.4`
> **Branch audited:** `feature/0.5.0` == `develop` == `origin/develop` @ `803238c`
> **Baseline:** `specs/audits/20260823T145726Z-4db47555/consolidated-audit.md` — score **3.6 / 10**, findings DRIFT-01..31
> **Rubric:** `dd-audit-project`, six dimensions A–F, weighted average with floor cap
> **Method:** read-only throughout. No repo file modified outside this audit directory; no `terraform` apply/plan against a real backend; AWS / Databricks / GitHub calls are read-only; no secret **value** read (secret **names** only). No sub-agent dispatch was available in this runtime — all seven lanes were executed directly by `project-auditor`, time-boxed.
> **Redaction:** the repository is PUBLIC. Account ids, resource ids, e-mail addresses and absolute local paths are replaced by placeholders (`<account-id>`, `<vpc-id>`, `<operator-email>`, `<workspace>`, `<state-bucket>`, `<lock-table>`).

---

## 1. Verdict

**The remediation is real and nearly complete in code; it is roughly half-landed live; and it shipped one self-inflicted blocker that disables the very control plane the release exists to restore.**

- **24 of 31 baseline findings are closed in code**, 14 of them end-to-end including live state. The capture lane is gone from the workflows and from `services/`; the supply chain is hash-locked with zero tracked binaries; one version axis; `ruff`/`mypy`/143 tests all green; the two April state locks are released; 24 leaked security groups and the empty ECS cluster are deleted; all four Databricks pipelines are deployed to `dev` and `hml` matching the repo.
- **One CRITICAL regression was introduced by the release itself.** `.github/workflows/plan_on_pr.yml` is **not valid YAML** at `HEAD` and on `origin/develop`. GitHub's workflow registry confirms the parse failure by listing the workflow under its own file path instead of a name. The workflow that carries `actionlint`, `ruff`, `mypy`, the three test suites, `pip-audit` and every per-stack plan therefore cannot run — which re-opens DRIFT-14 (CI safety guards exist, nothing executes them) and blocks AC-4, AC-7 (the required-check name comes from that workflow's first run) and AC-9.
- **The backlog gate regressed.** `dadaia backlog doctor` now **fails** with one error: a backlog entry's subject ref points at `apps/dabs/job_ddl_setup/...`, a path this release deleted. AC-25 requires it clean.
- **The live cut-over is genuinely operator-gated and correctly documented.** The four OIDC role ARNs are published as repository variables, but the roles themselves do not exist — `prd/00_bootstrap` has not been applied. Ten runbook steps remain in `docs/runbooks/v0.5.0-live-cutover.md`, each with a stated precondition and proof.
- **Memory is intentionally one release behind.** The atoms were rewritten at the v0.4.0 closure this morning and describe the pre-v0.5.0 world (the CI auth gap, 158 tests, the capture-layer atom). `T-E.5` updates them in CLOSURE. This is scheduled, not drift — but it is the state today, and it is scored as such in the live column.

**Ship gate (`SPEC.md` §4): re-audit ≥ 7 with no dimension < 5.** Official score **6.1** — the gate is **not** met. Projected score once the two code defects are fixed and the runbook is executed: **7.4** — the gate is met with margin.

---

## 2. Compliance scorecard

Two columns, per the re-audit brief. **(a) code/repo** = what a fresh clone plus a functioning CI would be once the bootstrap apply lands; live-pending items are treated as landed, genuine code defects are **not**. **(b) live** = the platform as it actually stands this evening. **(b) is the official score.**

| Dim | Dimension | (a) code/repo | (b) live — **official** | Rationale |
|---|---|---|---|---|
| A | Architecture | **8** | **6** | Code: `services/` reduced to 8 root stacks + 4 modules, zero `kinesis\|firehose\|sqs` matches, the 524-line PRD monolith and both ECS shells deleted, 8/8 `.terraform.lock.hcl`, `required_providers` everywhere. Live: the deployed estate still carries the deleted architecture — 8 state keys for destroyed stacks, 2 firehose roles, 4 Databricks cross-account/cluster roles, the unmanaged legacy VPC shell, 63 ACTIVE task-definition revisions. The capture-deprecation ADR (`T-E.4`) and `architecture.md` (`T-E.5`) are CLOSURE work, not yet written. |
| B | Product | **6** | **5** | The catalogued product feature `cicd-pipeline` is **broken in the clone**: `plan_on_pr.yml` cannot parse, so the flagship deliverable of WS-A is non-functional for any consumer (RES-01) — that caps the code column too. Live adds: 11 orphan Databricks jobs from deleted bundles, the hourly ingestion schedule still ENABLED, the legacy dev lambda still present. Positive: 4 pipelines deployed `dev`+`hml` == repo, 7 surviving bundles validate clean. |
| C | Tech stack | **8** | **8** | Dependency confusion closed (0 public `dm-chain-utils==` pins; `pip install ./utils --no-deps` path install + `--require-hashes -r apps/lambda/requirements.lock`), 0 tracked `*.zip`/`*.whl`, `.lambda_zip/` gitignored, one version axis (`VERSION`, both library declarations and all bundle `VERSION` files = `0.5.0`, zero old-axis hits outside a `utils/README.md` sentence that documents the change), `ruff` + `mypy` configured and clean. Only `tech-stack.md` lags, by CLOSURE design. |
| D | Security | **8** | **6** | Code: static keys and every capture-era secret are gone from the secret store; the bootstrap IAM policy carries prefix-scoped allows plus an explicit self-mutation `Deny` and passed `security-reviewer` rev3; the rc-1 HIGH (plaintext UC ExternalId default) was fixed forward and the push verdict for `803238c` is APPROVED; no personal identifier or workspace host survives in `apps/dabs/`. Live: least privilege is **unproven** — AC-2/AC-2b cannot be executed because the roles do not exist; dead-but-privileged roles remain; the live Databricks estate still runs as `<operator-email>` while the `dm_spn_user` service principal sits unused. |
| E | Tests | **7** | **6** | 143/143 green in ~6 s across four suites (`tests/lambda`, `tests/dabs` incl. a DLT expectations contract, `tests/utils`, `scripts/ci/tests`); the retired-code suite is gone; no skips, no quarantine, no tombstones. Live deduction: **no suite is executed by CI** — the last workflow run of any kind was 2026-04-11, and the workflow that would run them cannot parse. `T-D.2` (the `qa-engineer` deletion-map verdict) is still an open marker although the deletions in `T-D.3` are already committed — an ordering inversion against O-7. |
| F | Design / serving | **8** | **6** | Code: dashboards parametrised off the hard-coded `dev.` catalog, embed setting aligned, `run_as` set to the service principal, `validate -t prod` fails with the host unset. Live: the `hml` storage credential and external location (`T-C.7`) do not exist yet, so the `hml` lane's dashboards have no resolvable data; the stale `.bundle/dd-chain-explorer` root and one orphan dashboard survive. |

**Aggregation** (`weighted = A·0.20 + B·0.25 + C·0.15 + D·0.20 + E·0.15 + F·0.05`; `final = min(weighted, floor + 2)`):

| | A | B | C | D | E | F | weighted | floor | **final** |
|---|---|---|---|---|---|---|---|---|---|
| (a) code/repo — **projected** | 8 | 6 | 8 | 8 | 7 | 8 | 7.35 | 6 | **7.4 / 10** |
| (b) live — **OFFICIAL** | 6 | 5 | 8 | 6 | 6 | 6 | 6.05 | 5 | **6.1 / 10** |

Baseline was **3.6 / 10**. Delta: **+2.5 official**, **+3.8 projected**. No dimension breaches the floor of 3; no mandatory escalation. Recommendation band `6 ≤ final < 8` → **minor-to-moderate drift, address in the next release**; here the "next release" is the completion of this one — the two code defects are single-commit fixes and the rest is the runbook.

**Ship-gate arithmetic:** official 6.1 < 7 → **blocked**. Every dimension is ≥ 5, so no dimension-floor breach. Fixing RES-01 and RES-02 alone lifts B by roughly one point in both columns; executing the runbook lifts A, D, E and F. The projected 7.4 clears the gate.

---

## 3. DRIFT-01..31 status table

Statuses: **FIXED (code+live)** · **FIXED-CODE, LIVE-PENDING (step n)** — `n` is the step in `docs/runbooks/v0.5.0-live-cutover.md`; where the remainder is CLOSURE work rather than a live operation it is marked **CLOSURE-PENDING (task)** · **OPEN** · **DEFERRED (slug)**.

| ID | Status | Evidence command → result |
|---|---|---|
| DRIFT-01 CI cannot authenticate | **FIXED-CODE, LIVE-PENDING (step 1)** — also blocked by RES-01 | `gh variable list` → 4 rows, `AWS_DEPLOY_ROLE_{DEV,HML,PRD,READONLY}`, non-empty role ARNs, set 17:05Z. `aws iam list-roles --query "Roles[?contains(RoleName,'gha')].RoleName"` → **empty**; `aws iam list-attached-role-policies --role-name dm-chain-explorer-gha-deploy-dev` → `NoSuchEntity`. The variables point at roles that do not exist until `prd/00_bootstrap` is applied. |
| DRIFT-02 deploy workflow re-provisions capture | **FIXED (code+live)** | `grep -rniE 'kinesis\|firehose\|sqs\|ecs\|onchain-stream' .github/workflows/ scripts/ci/` → 7 hits, **all benign**: 5 are the substring `ecs` inside `age_secs`/`max_age_secs` in `tf_state_lock_check.sh`, 2 are comments recording the retirement. Zero provisioning references. |
| DRIFT-03 v0.4.0 done-but-open | **FIXED (code+live)** | `git log -1 -- specs/memory/` → `d507f78 chore(release): close and archive v0.4.0 — memory update (11 atoms + catalog), CLOSURE Aprovado, ACTIVE freed`; `cat specs/releases/ACTIVE.md` → `release: v0.5.0 / phase: IMPLEMENTATION`; `dadaia specs doctor` → 0 errors. |
| DRIFT-04 six stale memory atoms | **FIXED-CODE, CLOSURE-PENDING (`T-E.5`)** | Atoms rewritten at v0.4.0 closure (`d507f78`). They still describe pre-v0.5.0 truth by design: `grep -n 'Gap — CI cannot authenticate' specs/memory/tech-stack.md` → line 137; `quality-assurance.md:42` → "158 tests, 158 green" vs 143 today. `catalog.json` = 6 entries, `product/*.md` = 6 feature atoms + `index.md` → consistent. |
| DRIFT-05 audits undispositioned | **FIXED-CODE, CLOSURE-PENDING (`T-E.8`)** | `SPEC.md` §7 gives 31/31 + 82/82 dispositions. `dadaia specs doctor` → `[WARN] SPEC-DOC-038` × 2: both audit directories still loose in `specs/audits/`; archive happens at CLOSURE. |
| DRIFT-06 dependency confusion | **FIXED (code+live)** | `grep -rn 'dm-chain-utils==' . --exclude-dir=.git --exclude-dir=specs` → **0**. `scripts/build_lambda_layer.sh` present (4.5 KB) with `apps/lambda/requirements.lock` (15.7 KB). |
| DRIFT-07 committed layer zip, 31 CVEs | **FIXED (code+live)** | `git ls-files '*.zip' '*.whl' \| wc -l` → **0**; `git check-ignore -v .lambda_zip/` → `.gitignore:101`. |
| DRIFT-08 admin-escalating deploy roles | **FIXED-CODE, LIVE-PENDING (steps 1–2)** | Bootstrap stack authored, `security-reviewer` rev3 APPROVED (handoff `…T-A2` rev3). `aws iam list-roles` gha → empty, so AC-2 and AC-2b (`simulate-principal-policy`) are **unexecutable** today; the old `prd/03_iam/oidc.tf` removal is a pending apply (step 2). |
| DRIFT-09 public-repo secrets + personal identifier | **FIXED-CODE, LIVE-PENDING (step 8)** | `gh secret list` (names only) → 7 secrets, all `DATABRICKS_*`; **no** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `DYNAMODB_TABLE`, `ECS_TASK_*`, `HML_VPC_ID`, `HML_SUBNET_ID`. Repo-wide tracked scan for personal-mail patterns → 0; `grep -rnoE '<mail-pattern>\|<workspace-host-pattern>' apps/dabs/` → **0**. Live residual: `databricks pipelines list-pipelines` and `jobs list` still report `<operator-email>` as `creator_user_name`/`run_as_user_name` (RES-05). |
| DRIFT-10 no branch protection, default branch | **FIXED-CODE, LIVE-PENDING (step 10)** | `gh repo view --json defaultBranchRef,visibility` → `{"name":"master"}`, `PUBLIC`. `gh api …/branches/main/protection` → 404 *Branch not found*; `…/branches/develop/protection` → 404 *Branch not protected*. `gh api …/contents/.github/workflows/drift_detection.yml?ref=main` → 404. `gh api …/environments` → `dev`, `hml`, `production` — **no `hml-apps`** (that half is met). |
| DRIFT-11 two version axes | **FIXED (code+live)** | `cat VERSION` → `0.5.0`; `cat apps/dabs/*/VERSION \| sort -u` → `0.5.0`; `utils/pyproject.toml:7` and `utils/src/dm_chain_utils/__init__.py:9` → `0.5.0`; `grep -rn '0\.2\.9' --exclude-dir=specs` → 1 hit, a `utils/README.md` sentence documenting the collapse. Tag `v0.5.0` is minted at ship (`git tag --list 'v0.5.0'` → empty, expected). |
| DRIFT-12 16 dead Python modules | **FIXED (code+live)** | `git ls-files apps/docker` → **0 tracked files**; `grep -rn 'dm_kinesis\|dm_sqs\|dm_firehose\|dm_web3_client\|dm_cloudwatch_logger\|api_keys_manager' --include='*.py' .` → **0**. (Untracked directory shell survives on disk → RES-13.) |
| DRIFT-13 dead IaC | **FIXED-CODE, LIVE-PENDING (step 7)** | `grep -rniE 'kinesis\|firehose\|sqs' services/` → **0**. `ls -d services/*/*/` → 8 root stacks (`dev/01_peripherals`, `dev/02_lambda`, `hml/04_peripherals`, `prd/{00_bootstrap,01_tf_state,03_iam,04_peripherals,06_lambda}`) + 4 modules. `terraform fmt -check -recursive services/` → clean. Live: 8 state keys for destroyed stacks remain (RES-06). |
| DRIFT-14 CI safety tests never run, stack map lies | **OPEN** (regressed by RES-01) | `pytest tests scripts/ci/tests -q` → **143 passed**, of which `scripts/ci/tests` contributes 7 test modules — the guards exist and are green locally. But `actionlint .github/workflows/*.yml` → `plan_on_pr.yml:83:0: could not parse as YAML`, and `gh api …/actions/workflows` lists that workflow under its own path rather than a name. **No workflow can execute the guards.** Last CI run of any kind: 2026-04-11. |
| DRIFT-15 no concurrency, no lock files, destroy gaps | **FIXED (code+live)** | `grep -L 'concurrency:' .github/workflows/*.yml` → **no output** (all 6 declare it); `auto-bump-version.yml` absent from `ls .github/workflows/`; `git ls-files 'services/**/.terraform.lock.hcl' \| wc -l` → **8**, equal to the 8 surviving root stacks (AC-15 met). |
| DRIFT-16 two stale state locks | **FIXED (code+live)** | `aws dynamodb scan --table-name <lock-table> --query 'length(Items[?Info!=null])'` → **0**. (Total item count 16 = MD5 digest rows, not locks.) |
| DRIFT-17 24 leaked SGs in the unmanaged VPC | **FIXED-CODE, LIVE-PENDING (step 6)** | `aws ec2 describe-security-groups --filters Name=group-name,Values=dm-hml-sg-* --query 'length(SecurityGroups)'` → **0** (26 deleted, incl. 2 legacy). `aws ec2 describe-vpcs --filters Name=tag:Name,Values=ChainExplorer-vpc` → `<vpc-id>` **still present** — expected: IGW/route-table/VPC deletion is runbook step 6. |
| DRIFT-18 Databricks deploy drift | **FIXED (code+live)** | `databricks pipelines list-pipelines` → exactly 4: `[dev] dm-app-logs`, `[hml] dm-app-logs`, `[dev] dm-ethereum`, `[hml] dm-ethereum`, all IDLE. `T-C.6` recorded 14 bundle deploys and a notebook export diff of 0 against the repo for the Fluent-Bit reader. |
| DRIFT-19 broken / no-op DABs assets | **FIXED-CODE, LIVE-PENDING (step 8)** | `ls apps/dabs/` → 7 bundles; `job_trigger_all`, `job_full_refresh`, the `alert_*`/`genie_*` bundles and `job_reconcile_orphans` are all absent. `databricks bundle validate -t dev` (dlt_ethereum) → **rc 0**, 1 warning. Live: `databricks jobs list` → **17 jobs**, of which **11 are orphans** of deleted bundles, including a still-scheduled `dm-reconcile-orphan-blocks` (RES-04). |
| DRIFT-20 inverted test pyramid | **FIXED (code+live)** | `pytest` → 143 passed / 0 skipped. Suites: `tests/lambda` (2 modules), `tests/dabs` (2, incl. `test_dlt_expectations_contract.py`), `tests/utils` (3), `scripts/ci/tests` (7). The 113 retired-code tests are gone. Residual marker inversion → RES-15 note in §5. |
| DRIFT-21 hourly ingestion burning quota | **FIXED-CODE, LIVE-PENDING (step 5)** | `aws scheduler list-schedules` → `dm-dd-chain-explorer-prd-contracts-ingestion-hourly` **ENABLED** — expected until `prd/06_lambda` is applied. |
| DRIFT-22 HML half-alive | **FIXED-CODE, LIVE-PENDING (steps 3–4, 6–7)** | `aws logs describe-log-groups --log-group-name-prefix /hml` → 0, but `…contains(logGroupName,'hml')` → **30** groups still live. State bucket still holds `hml/{ecs,vpc,iam,databricks,databricks-workspace,peripherals}` keys. `T-C.7` (hml UC storage credential + external location) is an open task. |
| DRIFT-23 capture ECR state + KMS | **DEFERRED (`capture-ecr-state-and-kms-ownership-transfer`)** | `aws s3api list-objects-v2 --bucket <state-bucket>` → `capture/ecr/terraform.tfstate` still present, as designed; `aws ecr describe-repositories` → `airflow`, `dd-chain-capture-stream`, `dd-chain-capture-connect` — all owned by `dd-chain-capture`, **no** `onchain-*` repo. Ownership transfer routes to backlog via `T-E.7`. |
| DRIFT-24 live orphans (lambda, roles, log groups) | **FIXED-CODE, LIVE-PENDING (steps 5–6)** | `aws lambda list-functions` → legacy `dd-chain-explorer-dev-gold-to-dynamodb` **still live** alongside the kept `dm-chain-explorer-gold-to-dynamodb-dev`. `aws iam list-roles` firehose → **2** (`dm-chain-explorer-firehose-role-hml`, `dm-hml-firehose-role`). `aws logs describe-log-groups --log-group-name-prefix /aws/lambda/dm-` → retention `None` on all 3 kept groups (RES-09). `aws ecs list-task-definitions --status ACTIVE` → **63**. |
| DRIFT-25 prod target, dashboards, DDL/maintenance jobs | **FIXED-CODE, LIVE-PENDING (step 8)** | `T-C.3`/`T-C.4` committed; `grep -rnoE '<mail-pattern>\|<workspace-host-pattern>' apps/dabs/` → 0; dashboards render per catalog. Live: `dm-ddl-setup`, `dm-dm-delta-maintenance`, `dm-check-tables` (both targets) are part of the 11 orphan jobs awaiting bulk deletion. |
| DRIFT-26 security hardening batch | **FIXED (code+live)** | `security-reviewer` push verdict for `803238c`: **APPROVED**, "No CRITICAL/HIGH finding in the delta", 5 informational findings. The rc-1 HIGH (plaintext UC ExternalId default) is fixed forward — 0 UUID-shaped defaults at HEAD, ExternalId supplied as `TF_VAR` from a repository secret (`DATABRICKS_UC_EXTERNAL_ID`, created 17:58Z). |
| DRIFT-27 possibly-dead gold→DynamoDB chain | **FIXED-CODE, CLOSURE-PENDING (`T-E.5`)** | The chain is deliberately kept; the silver filter was retargeted off the retired producers' logger names in `T-C.4`. The "consumer-unverified" documentation lands with the memory update. |
| DRIFT-28 docs cite 16 nonexistent targets | **FIXED (code+live)** | `make -n` on all 10 target families cited in `README.md`, `docs/`, `apps/*/README.md` → **every one resolves** (`help test lint typecheck check build_lambda_layer dabs_validate_all tf_plan dev_tf_plan prd_bootstrap_apply`; the earlier "broken" hits were a grep artifact — the citations use `_`-suffixed target names). `grep -rniE 'kinesis\|firehose\|ECS producer' README.md docs/ apps/*/README.md` → 3 hits, all legitimate: one negative statement in `README.md:11` and two runbook lines that delete a firehose role. `git ls-files 'img/*'` → 0. |
| DRIFT-29 no quality gates, polluted worktree | **FIXED (code+live)** | `ruff format --check . --no-cache` → *71 files already formatted*; `ruff check . --no-cache` → *All checks passed!*; `mypy` → *Success: no issues found in 5 source files*; `git status --porcelain` → **empty**. Untracked-but-physical state directories remain → RES-12. |
| DRIFT-30 backlog structure | **OPEN** (regressed) | `dadaia backlog doctor` → `[ERROR] BL-SCHEMA [dashboards-analytics-enrichment] subject ref 'apps/dabs/job_ddl_setup/src/…/setup_ddl.py#main' (kind=code) resolves to no known anchor` → **FAILED: 1 error**. The single-source `BACKLOG.md` + `_archive/` layout is correct, but the release deleted a path a backlog entry still points at. AC-25 not met. |
| DRIFT-31 stub constitution, misfiled bug | **FIXED (code+live)** | `T-E.1` authored the constitution (`[x]`); `dadaia bugs status` → `[ok] 0 open bug(s)` (AC-28 met). |

### 3.1 Counts

| Status | Count | Ids |
|---|---|---|
| **FIXED (code+live)** | **14** | 02, 03, 06, 07, 11, 12, 15, 16, 18, 20, 26, 28, 29, 31 |
| **FIXED-CODE, LIVE- or CLOSURE-PENDING** | **14** | 01, 04, 05, 08, 09, 10, 13, 17, 19, 21, 22, 24, 25, 27 |
| **OPEN** | **2** | 14 (regressed by RES-01), 30 (regressed by a deleted path) |
| **DEFERRED (backlog)** | **1** | 23 → `capture-ecr-state-and-kms-ownership-transfer` |

Of the 14 pending, **12 are live operations** covered by the runbook and **2 are CLOSURE authorship** (`T-E.5` memory truth, `T-E.8` audit archive).

---

## 4. Acceptance-criteria roll-up (`SPEC.md` §4)

| Verdict | Count | ACs |
|---|---|---|
| MET | 14 | AC-1, AC-3, AC-3b, AC-5, AC-6, AC-8, AC-13, AC-15, AC-17, AC-19 (code), AC-20, AC-21, AC-22, AC-24, AC-26, AC-28 |
| MET-CODE, LIVE-PENDING | 9 | AC-2, AC-2b, AC-7, AC-10, AC-11, AC-12, AC-14, AC-16, AC-18b |
| PARTIAL | 3 | AC-9 (suite green, not executed by CI), AC-18 (pipelines match; 11 orphan jobs live), AC-23 (suite green; `qa-engineer` deletion-map verdict marker open) |
| **NOT MET** | 3 | **AC-4** (`plan_on_pr` unparseable + no `main`), **AC-7b** (no committed stale-branch listing artifact), **AC-25** (`backlog doctor` fails) |
| CLOSURE-scheduled | 1 | AC-27 (dispositions + audit archive) |

AC-4b was not independently re-verified in this pass (time-boxed); `T-A.8` is `[x]` and its `scripts/ci/tests` cases are among the 143 green.

---

## 5. Residual findings

15 items, severity-ordered. The operator-gated live work is deliberately collapsed into **one** finding group (RES-03).

| ID | Sev | Finding | Owner | Disposition proposal |
|---|---|---|---|---|
| RES-01 | **CRITICAL** | `.github/workflows/plan_on_pr.yml` is invalid YAML at `HEAD` and on `origin/develop`. A multi-line unquoted `name:` whose continuation contains `: ` breaks the mapping at line 83. `actionlint` → `could not parse as YAML`; `python3 -c "yaml.safe_load(...)"` → same, and the other 5 workflows parse. GitHub confirms: `gh api …/actions/workflows` lists this workflow under `.github/workflows/plan_on_pr.yml` instead of a name — the registry's signature for a file it cannot parse. Introduced by `9fe2a6c` (`fix(T-R.2): fold code-review rc-1 findings F-01..F-14`, 42 files). Blocks AC-4, AC-7's check naming and AC-9; re-opens DRIFT-14. | `software-engineer` | fixed-in-release — quote the `name:` on one line, re-run `actionlint`, re-push before the `main` cut-over |
| RES-02 | **HIGH** | `dadaia backlog doctor` fails: entry `dashboards-analytics-enrichment` carries a `kind=code` subject ref to `apps/dabs/job_ddl_setup/src/…/setup_ddl.py#main`, a path deleted by `T-C.4`. AC-25 requires a clean run. | `project-manager` (sole backlog owner) | fixed-in-release — repoint or alias the ref as part of CLOSURE |
| RES-03 | **HIGH** | **Operator-gated live cut-over, 10 steps, not executed.** `docs/runbooks/v0.5.0-live-cutover.md` steps 1–10: bootstrap apply (unblocks the 4 published role ARNs), `prd/03_iam` apply, HML reduction + dev role import, hml UC credential/external location, lambda layer + schedule disable, residual live deletions (VPC shell, 30 log groups, 63 task-def revisions, legacy lambda, 2 firehose roles), state-bucket hygiene, Databricks orphan sweep, fresh-clone plan proof, default-branch cut-over + protection. 12 of the 14 code-fixed-pending DRIFT items close here. | operator, then `software-engineer` | execute the runbook, then re-verify AC-2/2b, 7, 10–14, 16, 18b |
| RES-04 | MEDIUM | 11 orphan Databricks jobs from deleted bundles are live (`databricks jobs list` → 17 total; 6 legitimate). `dm-reconcile-orphan-blocks` remains **scheduled** with no notebook in repo or workspace. | `software-engineer` | fixed-in-release — runbook step 8 |
| RES-05 | MEDIUM | Live Databricks assets still carry `<operator-email>` as `creator_user_name`/`run_as_user_name` across 4 pipelines and 17 jobs. The `dm_spn_user` service principal exists (`databricks service-principals list` → 1 ACTIVE) but nothing runs as it. Code-side `run_as` is already the principal; Free Edition may not honour it on redeploy. | `software-engineer` | record-only if Free Edition blocks it; otherwise fixed-in-release at redeploy — either way state the constraint in `tech-stack.md` at CLOSURE |
| RES-06 | MEDIUM | `<state-bucket>` holds 16 keys, of which 8 belong to stacks this release deleted (`hml/{ecs,vpc,databricks,databricks-workspace,iam}`, `prd/{ecs,vpc,databricks-account,databricks-workspace}`) plus the cross-project `capture/ecr`. | `software-engineer` | fixed-in-release — runbook step 7; `capture/ecr` stays (DRIFT-23 deferred) |
| RES-07 | MEDIUM | Dead-but-privileged IAM survives: 2 firehose roles and 4 `dm-chain-explorer-databricks-{cluster,cross-account}-role-{hml,prd}` roles for a workspace destroyed in April. | `software-engineer` | fixed-in-release — runbook steps 3/6 |
| RES-08 | MEDIUM | 30 log groups matching `hml` (incl. one ECS container-insights group) and 63 ACTIVE task-definition revisions remain — pure noise and a resurrect-by-name surface. | `software-engineer` | fixed-in-release — runbook step 6 |
| RES-09 | MEDIUM | All 3 kept Lambda log groups report `retentionInDays: None` — unbounded retention. AC-12's tail clause is unmet until `T-B.14` imports them. | `software-engineer` | fixed-in-release — runbook step 5 |
| RES-10 | MEDIUM | The PRD hourly ingestion schedule is still `ENABLED` (`aws scheduler list-schedules`), burning Etherscan quota against an empty raw-data path. | `software-engineer` | fixed-in-release — runbook step 5 |
| RES-11 | LOW | AC-7b's committed stale-branch listing artifact does not exist: `git ls-files docs/` returns only `README.md` and 3 runbooks, while `gh api …/branches` lists **14** remote branches (11 stale). | `product-engineer` | fixed-in-release — a CLOSURE section satisfies the AC |
| RES-12 | LOW | Untracked but physically present inside the repo tree: `.hypothesis/`, `apps/docker/onchain-stream-txs/.hypothesis/`, and 7 `apps/dabs/*/.databricks/` directories (one with a nested `.terraform/`). Gitignored, so `git status` is clean and AC-22 passes — but the workspace law "repos stay clean" is about the working tree, not the index. | `software-engineer` | fixed-in-release — one `rm -rf` sweep at CLOSURE |
| RES-13 | LOW | `apps/docker/onchain-stream-txs/` survives on disk as an empty untracked shell. AC-20's "directory absent" is satisfied in git, not on disk. | `software-engineer` | fixed-in-release — same sweep as RES-12 |
| RES-14 | LOW | AC-5's pass condition (`0 matches`) is unreachable as written: the pattern matches the substring `ecs` inside `secs`, so `tf_state_lock_check.sh` alone yields 5 benign hits. The criterion is substantively met but literally unpassable. | `product-engineer` | record-only — tighten the pattern (`\becs\b`) when CLOSURE quotes the evidence |
| RES-15 | INFO | Two scheduled-not-drift observations: (a) all memory atoms describe pre-v0.5.0 truth (`tech-stack.md:137` still records the CI auth gap; `quality-assurance.md:42` still says 158 tests vs 143) — `T-E.5` closes this in CLOSURE; (b) `T-D.2` (the `qa-engineer` deletion-map verdict) is an open `[ ]` marker although `T-D.3`'s deletions are already committed, inverting O-7 — the `qa-engineer` rc-2 handoff does record an APPROVED verdict, so this is a marker-hygiene gap, not an unreviewed deletion. | `product-engineer` | record-only |

---

## 6. Process observations

- **No sub-agent dispatch was available in this runtime.** All seven evidence lanes were executed directly by `project-auditor` under a ~70-call budget. The baseline audit fanned out to 7 agents; this pass could not, which is why AC-4b and a full `pip-audit` re-run were dropped rather than faked. Earlier in the release, implementer sub-agents stalled on tool budgets and the coordinator absorbed their live steps — visible in `TASKS.md` as "Coordinator 2026-08-23: PARTIAL …" notes on `T-B.8`/`T-B.9`.
- **Classifier-gated live operations shaped the whole release.** Fourteen tasks are `[-]` "gated → operator runbook" because the session action policy refused the mutating AWS/Databricks calls (VPC deletion, bulk log-group deletion, `terraform apply`). The team's response — a 220-line runbook with per-step preconditions and proofs — is the right shape: the gate produced documentation instead of a silent stop. But it means the release's headline claim ("CI can authenticate") is true only of the repository, not of the account.
- **A broad sweep commit is where the CRITICAL regression entered.** `9fe2a6c` touched 42 files (+1407 / −527) folding 14 code-review findings at once. The unparseable workflow rode in on that sweep, was APPROVED by `code-reviewer` rc-2 and by the `security-reviewer` push verdict, and was pushed to `origin/develop` — because both reviews are diff-based prose reviews and neither parses workflow YAML. The one tool that would have caught it, `actionlint`, is wired **into the very workflow that cannot parse**. A pre-push `actionlint` invocation, or `make lint` covering `.github/`, closes this class permanently.
- **History was rewritten for a leaked default.** `security-reviewer` rc-1 REJECTED on a plaintext Unity-Catalog ExternalId committed as a Terraform variable default; the fix was carried forward with `cfb60c3` ("strip UC ExternalId defaults, TF_VAR via secret") and the push verdict for `803238c` records "0 UUID-shaped defaults anywhere at HEAD". The value now arrives from a repository secret created at 17:58Z. Worth noting for a PUBLIC repo: rewriting forward removes the value from `HEAD`, not from any fork or cached view of the earlier objects — treat the ExternalId as rotated, not as never-exposed.
- **`develop` was pushed mid-audit.** At the start of this session `develop` was 70 commits ahead of `origin/develop`; by 18:26Z the two are identical at `803238c`. The push carried RES-01 to the remote.

---

## 7. Recommended actions, ordered

1. **`software-engineer`** — fix `plan_on_pr.yml` (RES-01), prove with `actionlint` and a YAML parse, push. Nothing else in the ship gate can be evidenced until a workflow can run.
2. **`project-manager`** — repair the backlog subject ref (RES-02) so `dadaia backlog doctor` exits clean; AC-25 depends on it.
3. **Operator** — execute `docs/runbooks/v0.5.0-live-cutover.md` steps 1–10 (RES-03). Step 1 first: it is the precondition for the published role ARNs, for AC-2/AC-2b, and for every plan-based AC.
4. **`software-engineer`** — sweep the live orphans in the same window (RES-04, RES-06..RES-10) since they share the runbook's credential context.
5. **`product-engineer`** — CLOSURE: `T-E.4` ADR, `T-E.5` memory update to post-v0.5.0 truth, `T-E.6` `## Dispositions` (both audits), `T-E.7` intake candidates, `T-E.8` archive; include the stale-branch listing (RES-11) and tighten AC-5's pattern (RES-14).
6. **`software-engineer`** — physical worktree sweep (RES-12, RES-13) before CLOSURE.
7. **`project-auditor`** — re-run `T-R.4` after (1)–(4). Only then is the ≥ 7 / no-dimension-below-5 gate answerable on live evidence.

---

## 8. Evidence sources

- Baseline: `specs/audits/20260823T145726Z-4db47555/consolidated-audit.md` (7 lane reports, DRIFT-01..31)
- Release artifacts: `specs/releases/v0.5.0/{SPEC,PLAN,TASKS}.md`; `docs/runbooks/v0.5.0-live-cutover.md`, `docs/runbooks/00-bootstrap-apply.md`, `docs/runbooks/lambda-layer.md`
- Review handoffs consumed (`<workspace>/.dadaia/handoff/dd-chain-explorer/`): `2026-08-23T174409Z-security-reviewer-v050-rc1-review` (REJECTED, 11 findings), `2026-08-23T174516Z-code-reviewer-v050-rc1-review`, `2026-08-23T174551Z-qa-engineer-v050-rc1-review`, `2026-08-23T175530Z-qa-engineer-v050-rc2-review` (APPROVED), `2026-08-23T175730Z-software-engineer-rc1-blockers-and-qa-review`, `2026-08-23T182018Z-code-reviewer-v050-rc2-review` (APPROVED), `2026-08-23T182631Z-security-reviewer-push-verdict-develop-803238c` (APPROVED)
- Memory atoms read: `specs/memory/tech-stack.md`, `specs/memory/quality-assurance.md`, `specs/memory/product/catalog.json`, `specs/memory/product/cicd-pipeline.md`
- Commands executed this pass: `dadaia context show --json`, `dadaia specs doctor`, `dadaia backlog doctor`, `dadaia bugs status`; `pytest tests scripts/ci/tests -q -p no:cacheprovider`; `ruff format --check . --no-cache`; `ruff check . --no-cache`; `mypy`; `actionlint .github/workflows/*.yml`; `terraform fmt -check -recursive services/`; `make -n <target>` ×10; `git ls-files`/`git log`/`git status`/`git rev-list`; `gh variable list`, `gh secret list`, `gh repo view`, `gh api …/branches{,/main/protection,/develop/protection}`, `gh api …/environments`, `gh api …/contents/…?ref=main`, `gh api …/actions/workflows`, `gh workflow list`, `gh run list`; `aws iam list-roles/list-attached-role-policies/list-role-policies/list-users`, `aws ec2 describe-security-groups/describe-vpcs`, `aws ecs list-clusters/list-task-definitions`, `aws ecr describe-repositories`, `aws logs describe-log-groups`, `aws lambda list-functions`, `aws dynamodb list-tables/scan`, `aws events list-rules`, `aws scheduler list-schedules`, `aws s3api list-buckets/list-objects-v2`; `databricks pipelines list-pipelines`, `databricks jobs list`, `databricks service-principals list`, `databricks bundle validate -t dev`

---

## 9. Disposition status

| Finding set | Status |
|---|---|
| DRIFT-01..31 (baseline `20260823T145726Z`) | 14 FIXED · 14 FIXED-CODE pending live/CLOSURE · 2 OPEN (regressions) · 1 DEFERRED — `SPEC.md` §7 already assigns all 31 a terminal token; CLOSURE `## Dispositions` must reconcile DRIFT-14 and DRIFT-30 against the regressions recorded here |
| 2026-06-11 audit (70 findings / 82 lane ids) | dispositioned by `SPEC.md` §7.2; archival pending `T-E.8` |
| RES-01..RES-15 (this audit) | **open** — RES-01/RES-02 are in-release fixes, not new intake; RES-03 is the runbook; RES-05/RES-14/RES-15 are record-only and terminate here |

This audit archives to `specs/audits/_archive/` together with its baseline, once v0.5.0's CLOSURE gives every finding a terminal token and names the release.
