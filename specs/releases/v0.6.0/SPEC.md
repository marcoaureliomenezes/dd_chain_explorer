# SPEC — Release v0.6.0 — Three-repo segregation migration

> **Status:** Aprovado
> **Release ID:** v0.6.0
> **Owner:** product-engineer
> **Created:** 2026-08-23
> **Approved:** 2026-08-23 (mandatory pre-SPEC grill completed 2026-08-23, 2 rounds, frontier emptied, operator confirmed verbatim)
> **Consumes:** three-repo-segregation-migration
> **Provenance:** grill-me handoff `2026-08-23T203850Z-project-manager-grillme-3repo-segregation` (9 ADRs, operator-confirmed) · backlog item `three-repo-segregation-migration` (`specs/backlog/BACKLOG.md` `## ACTIVE`, approved intake) · v0.5.0 CLOSURE `## Intake candidates` (`specs/_archive/releases/v0.5.0/CLOSURE.md`) · v0.5.0 re-audit `20260823T182948Z-4db47555` (6.1 live / 7.4 projected)
> **Scope (operator-locked):** the repository topology of the platform. One repository becomes three: `dd-chain-infrastructure` (all Terraform + infra CI), a new hyphenated `dd-chain-explorer` (specs, DABs, Lambdas, library, tests), and `dd-chain-capture` (untouched). No product capability is added, changed or removed by this release.

---

## 1. Problem

v0.5.0 closed the remediation arc: CI authenticates under OIDC, the declared
infrastructure equals the live infrastructure, `main` is protected and the platform is
parked-by-design until `dd-chain-capture` delivers. It shipped through its own gate
(PR merged as a merge commit, tagged) and archived at
`specs/_archive/releases/v0.5.0/`. **v0.6.0 starts from that green baseline** (ADR-1) —
this release inherits a working platform and must hand it over without breaking it.

What v0.5.0 could not fix is **structural, not behavioural**: one repository owns three
unrelated concerns with three different audiences and three different blast radii.

- **The blast radius is undivided.** A Databricks notebook edit and an IAM role edit sit
  in the same working tree, behind the same branch protection, gated by the same nine
  status checks, deployed by the same four highly-privileged OIDC roles. A contributor
  who needs to fix a DLT expectation is handed the credentials to destroy the state
  bucket.
- **Visibility is unresolvable in one repository.** The platform's data-processing code
  is public-grade; its Terraform, state-key map and IAM topology are not. A single repo
  can be PUBLIC or PRIVATE — never both — so today the whole tree is public and every
  infrastructure decision is world-readable by default.
- **The repository name itself is legacy.** `dd_chain_explorer` (underscore) predates the
  hyphenated naming every sibling project uses, and it cannot be renamed into the target
  topology without carrying a history that mixes three concerns.
- **The spec context has no clean home.** `specs/` — the constitution, the memory atoms,
  eight archived releases and two archived audits — lives inside the repository that is
  about to be split, with no declared main repo.
- **Two v0.5.0 deferrals are stranded.** `T-B.14` (the `dm-chain-explorer-artifacts`
  bucket and the `prd/06_lambda` / `dev/02_lambda` layer rewire) and `T-B.7`'s
  Terraform-path schedule disable were deferred by operator ruling because they create a
  new productive PRD resource. They are exactly the seam this migration must define
  anyway — the Lambda artifact contract between the two new repositories.

This release changes **where code lives and who may deploy it**. It does not restart the
data flow, does not add a feature, and does not rewrite a pipeline.

---

## 2. Scope — IN (five workstreams)

Write sets are disjoint **by repository and by tree**. WS-I writes only inside
`dd-chain-infrastructure`; WS-X writes only inside the new `dd-chain-explorer`; WS-L
writes governance documents in both; WS-V writes evidence only; WS-D is operator-only and
writes nothing but repository settings. The legacy repository is **read-only after the
cutover** (§5 O-6).

### 2.1 WS-I — `dd-chain-infrastructure` (PRIVATE until validated)

**Goals**

| # | Goal |
|---|---|
| I1 | **Fresh repository skeleton, fresh git** (ADR-2). `git init` in the empty target repo — no history import, no `git remote add` of the legacy repo, no filter-branch. Branches `main` ← `develop` ← `feature/0.6.0`, the same branch law as today (`DADAIA.md` §4 Gitflow): `feature/{M.m.p}` pushable, `develop`/`main` PR-only. Root `VERSION` = `0.6.0`, `.gitignore`, `pyproject.toml` with the ruff/mypy configuration the CI test suite needs, and a new README describing this repo's single concern. |
| I2 | **Terraform moved as content, state untouched.** The eight surviving root stacks (`dev/01_peripherals`, `dev/02_lambda`, `hml/04_peripherals`, `prd/00_bootstrap`, `prd/01_tf_state`, `prd/04_peripherals`, `prd/06_lambda`) and the four modules (`cloudwatch_logs`, `dynamodb`, `lambda`, `s3`) move with **identical backend keys and identical resource addresses**, so every stack plans `0 to add, 0 to change, 0 to destroy` from the new repo. Committed `.terraform.lock.hcl` files travel with their stacks. **The empty `prd/03_iam` stack does not travel** — it declares no resource; its state key is removed instead of copied (v0.5.0 intake residual, folded here because a migration is the one moment the decision is free). |
| I3 | **The Lambda Terraform lives here; the Lambda code does not** (ADR-3). `prd/06_lambda` and `dev/02_lambda` consume the layer from the artifacts bucket through the `resolve_layer` contract — `layer_s3_key` + `layer_sha256` variables resolved by `scripts/ci/resolve_layer.sh`, never a working-tree path. The handler zips, which today are built by `data "archive_file"` from a source tree that no longer exists in this repository, become artifacts published by WS-X to the same bucket and resolved the same way. **No Python handler source, no `requirements.lock`, no layer build script exists in this repository.** |
| I4 | **The artifacts bucket lands** (absorbs v0.5.0 `T-B.14`). `dm-chain-explorer-artifacts` is declared in `prd/04_peripherals` — versioned, private, all public access blocked, encrypted — and **applied**. `dev` consumes the same bucket under a `dev/` prefix. The `prd/06_lambda` / `dev/02_lambda` layer rewire and the Lambda log-group imports ride the same apply. |
| I5 | **The PRD ingestion schedule is disabled through Terraform** (absorbs v0.5.0 `T-B.7`). The schedule is already `DISABLED` live via the scheduler API; this goal makes the declared state say so, so the plan stays clean. |
| I6 | **OIDC repointed** (ADR-4). `prd/00_bootstrap` gains a `github_repo` variable; the four deploy roles `…-gha-deploy-{dev,hml,prd}` and `…-gha-readonly-plan` re-trust `repo:<owner>/dd-chain-infrastructure:…` with their existing `sub` pinning (`:environment:<env>` per deploy role, `pull_request` + `refs/heads/{develop,main}` for the read-only role). A **new narrow role `…-gha-artifacts-publish`** is added, trusted to `repo:<owner>/dd-chain-explorer:…`, granting **only** `s3:PutObject`/`s3:PutObjectTagging`/`s3:AbortMultipartUpload` on `arn:…:<artifacts-bucket>/*` plus `s3:ListBucket` on the bucket — no other action, no other resource, and the project permissions boundary attached like every other project role. `00_bootstrap` remains **operator-applied, never CI-applied**. |
| I7 | **Databricks workspace infrastructure becomes Terraform by IMPORT** (ADR-5). A new stack declares the Unity Catalog **storage credentials**, **external locations** and **catalogs** that exist today, and adopts them with `terraform import` — **never** by create-then-destroy. A post-import plan showing `No changes` is the only accepted proof. DLT pipelines, workflows, jobs and dashboards stay DABs in the explorer repo and are **not** imported. |
| I8 | **Infra CI rewritten, not blind-copied.** The workflows that survive are the infrastructure lane only: plan-on-PR (fmt/validate/actionlint/zizmor/tests/per-stack `terraform plan -lock=false`), deploy, destroy, destroy-all, drift detection, Scorecard. `deploy_all_dm_applications.yml` does **not** travel — the application lane is WS-X's. `scripts/ci/**` and its pytest suite travel and are re-pointed at this repo's stack set; `stack_map.json` drops `prd/03_iam`. Four v0.5.0 security LOW residuals are fixed **in the rewrite, not after it**: the raw interpolation in the deploy workflow becomes an environment binding; the OIDC preflight masks the role ARN; a test pins the permissions boundary's `sts:` allowances against silent widening; a test pins `log_groups_describe_arn` to its single statement. |
| I9 | **Variables and the credential surface re-established.** `scripts/ci/publish_oidc_vars.sh` runs against the repointed bootstrap outputs and publishes `AWS_DEPLOY_ROLE_{DEV,HML,PRD,READONLY}` in this repository; the fail-fast preflight guards every role-assuming job. No static key, ever. |

**Write set:** everything inside the `dd-chain-infrastructure` repository · the
`prd/bootstrap` and per-stack Terraform state keys · live AWS resources already owned by
this project (artifacts bucket creation, log-group imports, the schedule's declared state,
the bootstrap role trust policies) · the `dd-chain-infrastructure` GitHub repository
settings (operator-gated, §2.6).

**Non-goals:** any Python handler or library source; any DABs bundle; any resource owned
by `dd-chain-capture`; the single-stack-tree restructuring (§3); creating any Databricks
object — I7 imports only.

### 2.2 WS-X — the new `dd-chain-explorer` (PUBLIC from birth)

**Goals**

| # | Goal |
|---|---|
| X1 | **Fresh repository skeleton, fresh git** (ADR-2), same branch law and the same `0.6.0` version axis as WS-I. Lean root: `pyproject.toml` (ruff + mypy + pytest configuration for this tree only), a Makefile that is thin wrappers over the scripts CI actually runs, `.gitignore`, and a **new README** — not the legacy one — describing the spec-context main repo and its two surfaces. |
| X2 | **Content migrated** (ADR-8, migration manifest): `apps/dabs/` (7 bundles), `apps/lambda/` (both handlers, `requirements*.txt`, the hash-checked lock), `utils/` (the three-module `dm-chain-utils` library), `tests/` (all four suites), `docs/runbooks/ci-security.md` and `docs/runbooks/lambda-layer.md`, `scripts/build_lambda_layer.sh`. Everything arrives as **content on a fresh git**, never as history. |
| X3 | **The Lambda artifact contract is published from here** (ADR-3). CI builds the layer (`pip install --require-hashes -r requirements.lock -t build/` plus `pip install ./utils -t build/ --no-deps` — the path install is the dependency-confusion closure) and the two handler zips, then uploads each to its content-addressed key under `s3://<artifacts-bucket>/…/<sha256>.zip` (dev under a `dev/` prefix) assuming **only** the `…-gha-artifacts-publish` role. The publish job emits the `<sha256>` values as its run output so the infrastructure repo's `resolve_layer` step can name them. |
| X4 | **Explorer CI.** Quality gate (`ruff format --check`, `ruff check`, `mypy`, `pytest -p no:cacheprovider`, `pip-audit -r` over the lock), the layer/handler build + publish job, `databricks bundle validate -t dev` and `-t hml` per bundle, and the DABs deploy lane behind the informed environment gate. `actionlint` + `zizmor` clean, every action SHA-pinned, `persist-credentials: false`, runner hardening — the v0.5.0 posture, reproduced. This repository has **no** Terraform workflow and **no** deploy role beyond `artifacts-publish`. |
| X5 | **Bundles validated and deployed from the new repo.** All 7 bundles validate in `dev` and `hml`; the `prod` target stays guarded (host variable with no default, `validate -t prod` fails when unset). Deployed workspace state equals the new repo, proven by notebook export diff. No bundle content changes in this release beyond the workspace-host/service-principal wiring the new repo's secret names require. |
| X6 | **`specs/` migrates as content at the cutover** (ADR-2). The **entire** tree — `constitution.md`, `memory/**`, `releases/**` (this release included), `backlog/**`, `bugs/**`, `audits/**` and **`_archive/**` in full** — is copied verbatim into this repository. This is the one task that defines C-DAY (§5 O-6); it is sequenced by WS-V, not by WS-X. |
| X7 | **Version axis.** Root `VERSION` and every `apps/dabs/*/VERSION`, plus the `dm-chain-utils` distribution version and `__init__.py` declaration, read `0.6.0`. One axis, both repositories, the SDD release id. |

**Write set:** everything inside the new `dd-chain-explorer` repository · the live
Databricks `dev` and `hml` targets · objects under the artifacts bucket's layer and
handler prefixes · the new `dd-chain-explorer` GitHub repository settings (operator-gated,
§2.6).

**Non-goals:** any Terraform file; any AWS resource other than putting objects in the
artifacts bucket; any deploy to a `prod` Databricks target; DLT data-quality or dashboard
enrichment (§3).

### 2.3 WS-L — laws, scoped `AGENTS.md` and cross-repo documentation

**Goals**

| # | Goal |
|---|---|
| L1 | **The new law, in `dd-chain-infrastructure`'s scoped `AGENTS.md`** (ADR-6), stated once and normatively: *infrastructure resources are created, changed and destroyed **only** by the CI pipeline applying Terraform — never by a console click, never by an ad-hoc CLI mutation.* The **only** documented exception is `services/prd/00_bootstrap`, which is applied by the operator with operator credentials and which CI may never apply. A CLI mutation outside that exception is a defect to be registered, not a shortcut. |
| L2 | **The mirror law, in the new `dd-chain-explorer`'s scoped `AGENTS.md`**: this repository declares **no** infrastructure; it publishes artifacts and deploys Databricks bundles. Terraform belongs to `dd-chain-infrastructure`; capture belongs to `dd-chain-capture`. It also records that this repository is the **main repo of the spec context** — `specs/` is authoritative here — and that it is PUBLIC, so nothing that is not public-grade may be committed. |
| L3 | **The cross-repo contract document**, authored in the new explorer's `docs/`: the artifacts contract (which bucket, which prefixes, which content-addressed key shape, who publishes, who resolves), the OIDC role map (five roles, which repo each trusts, what each may do), the Databricks split (workspace infra = Terraform-by-import in the infrastructure repo; DLT/workflows/dashboards = DABs here), and the three-repo boundary diagram. Runbooks that travel are re-pointed at their new repository. |
| L4 | **`specs/constitution.md` amended** to the three-repo topology before the cutover, so it travels as content already correct: the repository boundary, the two laws of L1/L2, and the statement that `specs/` is authoritative in the new explorer repository. |

**Write set:** `AGENTS.md` in both new repositories · the new explorer's `docs/**` ·
`specs/constitution.md` (in the legacy repo before C-DAY, in the new explorer after).

**Non-goals:** editing the workspace-level `DADAIA.md` or any projected law file
(`DADAIA.md` §8 — human-only); writing memory atoms outside CLOSURE (§8).

### 2.4 WS-V — validation, cutover and the release gates

**Goals**

| # | Goal |
|---|---|
| V1 | Both repositories' CI green on `feature/0.6.0`, then green on the definition PR into `develop`. |
| V2 | **Drift proof:** every stack plans `0 to add, 0 to change, 0 to destroy` from a **fresh clone** of `dd-chain-infrastructure`, including the imported Databricks UC stack and the newly applied artifacts bucket. |
| V3 | **Unity Catalog proof:** the imported storage credentials and external locations validate; both hml buckets answer `head-bucket`; every bundle validates in `dev` and `hml` and deployed state equals the new explorer repo. |
| V4 | **The migration manifest checklist is 100 % verified** — every row of §6 is either *arrived at its destination* or *deliberately dead*, each with evidence. This checklist is the precondition of both the cutover and, later, the operator's deletion of the legacy repository (ADR-7). |
| V5 | **C-DAY — the cutover** (§5 O-6): `specs/` handed over to the new explorer repo as content; the legacy `specs/` tree frozen; a tombstone commit in the legacy repo pointing at both successors. |
| V6 | **alpha-1** — every workstream implemented and closed by a `qa-engineer` review. |
| V7 | **rc-1** — the full trio (`qa-engineer`, `code-reviewer` six-axis on the delta, `security-reviewer` diff-based) APPROVED, in **both** repositories. |
| V8 | **Ship** — memory update → CLOSURE → archive **in the new explorer repository**, PR `develop` → `main` in both repos, CI watched to green, then the operator's final validation (ADR-7, ADR-9). |

**Write set:** `.dadaia/handoff/**` and `.dadaia/reports/**` evidence · `specs/**` in
whichever repository is authoritative at that moment (§5 O-6) · no production file.

**Non-goals:** implementing anything WS-I/WS-X own; deleting the legacy repository (WS-D).

### 2.5 WS-D — legacy decommission (OPERATOR-ONLY)

**Goals**

| # | Goal |
|---|---|
| D1 | Legacy credential surface cleaned: the `dd_chain_explorer` repository's variables, secrets and environments removed once both successors are green — nothing may still be able to deploy from the legacy repo. |
| D2 | **`dd-chain-infrastructure` flipped PRIVATE → PUBLIC** (ADR-9) **only** after the operator's own validation, and only once a fresh secret-scan of the whole tree is clean. |
| D3 | **The legacy repository `dd_chain_explorer` is deleted** (ADR-7) — an operator act, permitted only after V4's manifest is 100 % verified, both new repositories are CI-green, and the operator has validated. No agent deletes it, and no agent may propose deleting it earlier. |

**Write set:** GitHub repository settings and existence, exclusively by the operator.

**Non-goals:** everything else.

### 2.6 Operator-gated surface (the release's hard boundary)

Agents author; the operator executes anything holding a secret value, changing repository
settings, or destroying. Every such step is flagged `OPERATOR-ONLY` in `TASKS.md`:
repository creation settings and visibility; branch protection and required checks;
environments `dev` / `hml` / `production` with their reviewers and deployment-branch
policies; all secret **values** (Databricks host/token, any environment secret); the
`prd/00_bootstrap` apply; the legacy repo's secret cleanup; and the legacy repo's
deletion.

---

## 3. Scope — OUT

| Out of scope | Reason |
|---|---|
| `dd-chain-capture` — any file, resource or setting | Third repository, unchanged by this migration (ADR-8) |
| Git **history** migration of any kind (import, graft, filter-branch, subtree split) | ADR-2: fresh git in both repos; specs migrate as content. History stays reachable in the legacy repo until the operator deletes it |
| Any product capability change — new feature, pipeline rewrite, dashboard enrichment, DLT data-quality work | This release moves code; it does not change what the platform does |
| Restarting the data flow / un-pausing DLT triggers / any backfill | Parked until `dd-chain-capture` delivers (ADR-007 in `specs/memory/architecture.md`) |
| Creating **any** Databricks workspace object | WS-I I7 imports what exists; creation would be exactly the recreation ADR-5 forbids |
| `terraform-single-stack-tree-per-env-tfvars` (collapse dev/hml/prd into one tree + per-env tfvars) | Restructuring, not migration. Stays backlog — doing it during a repo move would make the 0-diff proof (V2) undecidable |
| `capture-ecr-state-and-kms-ownership-transfer` | Owned by `dd-chain-capture`; routed there. The state key travels with the state bucket and is documented, not moved |
| `rest-api-public-endpoint` | Own planning session; unrelated to topology |
| `encryption-at-rest-posture-decision`, `s3-raw-lifecycle-intelligent-tiering` | No new data at rest; prefix layout still unconfirmed |
| `dlt-ethereum-data-quality-enhancements`, `dashboards-analytics-enrichment` | Need flowing data |
| Alert / Genie Databricks asset reinstatement | The CLI still has no resource type for either |
| `zizmor --offline` posture decision; `harden-runner` audit → block mode | Posture decisions the operator has not taken; the migration reproduces today's posture verbatim rather than silently changing it |
| `DescribeLogGroups` path-prefix narrowing | Waits on an AWS capability, not on us |
| Rotate-or-accept the public Databricks account UUID | Operator decision; the value is the account's UC external id and is already public |
| Any dependency on the dadaia-workspace multi-repo spec-context feature | In flight in another session (§9). The structure below assumes it; **nothing here blocks on it landing** |

---

## 4. Acceptance criteria

Every criterion is mechanically verifiable. `<artifacts-bucket>`, `<state-bucket>`,
`<owner>` are the values recorded in `specs/memory/product/aws-resources.md`; no account
id, host or personal identifier appears in any evidence artifact.

| AC | WS | Verification | Pass condition |
|---|---|---|---|
| AC-1 | I | `git -C <infra-clone> log --oneline \| wc -l`; `git log --format=%H \| tail -1` | history begins at this migration's own initial commit; **no** commit sha from the legacy repository exists in either new repo (ADR-2) |
| AC-2 | I | `ls services/prd services/dev services/hml services/modules` | the 7 surviving root stacks and 4 modules are present; `prd/03_iam` is **absent**; a `.terraform.lock.hcl` exists for every root stack |
| AC-3 | I | `terraform plan` per stack from a **fresh clone**, in CI, under OIDC | `0 to add, 0 to change, 0 to destroy` on every stack — including `prd/06_lambda` and `dev/02_lambda` resolving the layer and handler artifacts from `<artifacts-bucket>` |
| AC-4 | I | `aws s3api head-bucket`, `get-bucket-versioning`, `get-public-access-block` on `<artifacts-bucket>` | 200; versioning `Enabled`; all four public-access blocks `true`; the bucket is declared in `prd/04_peripherals` (AC-3 clean plan proves it) |
| AC-5 | I | `aws scheduler get-schedule` for the contracts-ingestion schedule; AC-3's plan on the owning stack | `State: DISABLED` **and** declared so in Terraform |
| AC-6 | I | `aws iam get-role` × 5 + `get-role-policy`; `terraform show -json services/prd/00_bootstrap` | the 4 deploy roles' trust `sub` names `repo:<owner>/dd-chain-infrastructure:…`; `…-gha-artifacts-publish` exists, trusts `repo:<owner>/dd-chain-explorer:…`, and its **entire** policy is `s3:PutObject`/`PutObjectTagging`/`AbortMultipartUpload` on `<artifacts-bucket>/*` plus `s3:ListBucket` on the bucket; all 5 carry the project permissions boundary |
| AC-6b | I | `aws iam simulate-principal-policy` on `…-gha-artifacts-publish` | `s3:PutObject` on `<artifacts-bucket>/*` → `allowed`; `s3:GetObject` on the **state** bucket, `lambda:UpdateFunctionCode`, `iam:PassRole` → `implicitDeny` or `explicitDeny` |
| AC-7 | I | `terraform plan` on the Databricks UC stack immediately after the import | `No changes` — every credential, external location and catalog was **adopted**; `databricks storage-credentials get` / `external-locations get` show the same ids that existed before the release (nothing was recreated, ADR-5) |
| AC-8 | I | `gh workflow list` in the infrastructure repo; grep the workflow set | infrastructure lane only; no application-deploy workflow; every role-assuming job carries the preflight; `actionlint` + `zizmor` clean; the deploy workflow contains no raw interpolation of a value into a privileged step; the preflight does not print an unmasked role ARN |
| AC-9 | I | `pytest scripts/ci/tests -p no:cacheprovider` in CI | green, executed by CI; includes the new `sts:`-allowance pin and the `log_groups_describe_arn` single-statement pin; `stack_map.json` names exactly the surviving stacks |
| AC-10 | X | `git log` in the new explorer repo; `ls` its root | fresh history (AC-1); `apps/dabs/`, `apps/lambda/`, `utils/`, `tests/`, `docs/runbooks/`, `scripts/build_lambda_layer.sh`, lean `pyproject.toml`, Makefile and the **new** README present; **no** `services/` directory |
| AC-11 | X | the publish job log; `aws s3api list-objects-v2 --bucket <artifacts-bucket>` | the layer and both handler zips exist at content-addressed keys; the job assumed **only** `…-gha-artifacts-publish`; the layer was built from `./utils` as a **path** install plus `--require-hashes` third-party deps |
| AC-12 | X | `ruff format --check`, `ruff check`, `mypy`, `pytest -p no:cacheprovider`, `pip-audit -r` in the new repo's CI | all exit 0; the suite is the full four-suite set that was green at v0.5.0, minus the CI-script suite (which travelled to WS-I) — no test lost in the move without a `qa-engineer` verdict |
| AC-13 | X | `databricks bundle validate -t dev` and `-t hml` per bundle; `-t prod` with the host variable unset; notebook export diff per deployed pipeline | exit 0 for all 7 bundles in `dev` and `hml`; **non-zero** for `prod`; `diff` exit 0 for every deployed pipeline against its file in the **new** repo |
| AC-14 | X | `cat VERSION`; `cat apps/dabs/*/VERSION \| sort -u`; the library version declarations; `cat VERSION` in the infra repo | `0.6.0` everywhere, both repositories |
| AC-15 | X | `git -C <explorer-clone> ls-files 'specs/**' \| wc -l` compared with the legacy tree at C-DAY; `diff -r` of the two `specs/` trees | byte-identical `specs/` trees at C-DAY, `_archive/` included; nothing dropped, nothing rewritten |
| AC-16 | L | read `AGENTS.md` in both repos | the infrastructure repo states the CI+Terraform-only law with `prd/00_bootstrap` named as the **sole** operator-only exception; the explorer repo states it declares no infrastructure, is the spec-context main repo, and is PUBLIC |
| AC-17 | L | read the cross-repo contract doc | it names the artifacts bucket, the key shape, the publisher, the resolver, all five OIDC roles with their trusted repository, and the Databricks split; every migrated runbook points at its new repository |
| AC-18 | L | `wc -l specs/constitution.md`; read | the three-repo topology, both laws and the specs-authority statement are recorded |
| AC-19 | V | both repos' `feature/0.6.0` → `develop` PR checks | all checks green in **both** repositories |
| AC-20 | V | the §6 migration manifest checklist, committed as CLOSURE evidence | every row marked arrived-with-evidence or deliberately-dead-with-reason; **zero** unresolved rows |
| AC-21 | V | `git -C <legacy-clone> log -1`; `gh api` on the legacy repo's variables/secrets | the legacy repo's last commit is the tombstone; after WS-D, no variable, secret or environment remains that could deploy |
| AC-22 | V | secret scan over the whole tree of both new repos (denylist + `gitleaks`-class scan) | zero findings in either repo — the precondition of ADR-9's PUBLIC flip |
| AC-23 | V | `dadaia specs doctor` in the new explorer repo after C-DAY | 0 errors |
| AC-24 | V | drift-detection workflow in the infrastructure repo: `gh api …/contents/…?ref=main`, `gh workflow view` | present on the default branch and **enabled**; its first cron run is recorded as pending, never claimed as evidence |

**Ship gate (all must hold together):** AC-1..AC-24 green; both repositories' `develop` →
`main` PRs merged with CI green; the migration manifest 100 % verified (AC-20); the secret
scan clean in both repos (AC-22); and the **operator's explicit final validation** (ADR-7,
ADR-9). The legacy repository's deletion and the infrastructure repo's PUBLIC flip happen
**after** the gate, by the operator, and are recorded in CLOSURE as operator acts.

---

## 5. Ordering safety

| # | Rule |
|---|---|
| O-1 | **v0.5.0 first** (ADR-1). v0.5.0 is shipped, tagged and archived at `specs/_archive/releases/v0.5.0/`; this release starts from that commit and re-baselines nothing. |
| O-2 | **Bootstrap before everything CI does.** `prd/00_bootstrap` is repointed (`github_repo`) and the `artifacts-publish` role added, **security-reviewed**, then applied by the operator, and the four variables published in the new infrastructure repo — **before** any workflow run in either new repo is used as acceptance evidence. Until then both repos' CI can lint and test but cannot assume a role. |
| O-3 | **Bucket before publish before plan** (the artifacts chain). `<artifacts-bucket>` exists (I4) → WS-X publishes the layer and handler objects (X3) → only then may any Lambda-stack plan that resolves `layer_s3_key`/`layer_sha256` be treated as evidence (AC-3). |
| O-4 | **Import before any Databricks-infra plan is trusted** (ADR-5). The UC stack is written, `terraform import`ed for every existing object, and proven with a `No changes` plan (AC-7). If any object cannot be imported, the task **stops and escalates** — it never falls back to creating one. |
| O-5 | **Terraform leaves the legacy repo only after it plans clean from the new one.** The legacy tree is not modified during WS-I; it is simply abandoned at C-DAY. No window exists in which two repositories both claim a stack — CI can only deploy from the repository the bootstrap roles trust, and that flips exactly once (O-2). |
| O-6 | **C-DAY — the cutover point, executed as one step.** The moment WS-V's `specs/` handover commit lands in the new explorer repository (with both repos CI-green and the §6 manifest verified), the legacy repository's `specs/` tree is **FROZEN**: no marker flip, no memory write, no CLOSURE line is ever written there again. Every subsequent SDD write of this release — the remaining `[-]`→`[x]` flips, the memory atom updates and `CLOSURE.md` — happens in the **new** `dd-chain-explorer` repository. The legacy repo then receives exactly one further commit: the tombstone of V5. |
| O-7 | **No dual-write, ever.** Between the start of the handover task and its commit, no other task may write `specs/**` in either repository. The handover is the shortest possible critical section. |
| O-8 | **Tests travel before their subject is abandoned.** The four pytest suites arrive green in their destination repo before the legacy repo is treated as read-only; no test is dropped in the move without a `qa-engineer` verdict (`DADAIA.md` §7). |
| O-9 | **Deletion is last and is the operator's.** WS-D runs only after the ship gate (§4): D1 (credential cleanup) → operator validation → D2 (PUBLIC flip, gated on AC-22) → D3 (legacy repo deletion). Nothing in WS-D is agent-executable. |
| O-10 | **Secrets are never copied.** Secret **values** are re-entered by the operator in the new repositories. No agent reads, prints, transcribes or moves a secret value; only names are ever referenced (`DADAIA.md` §9). |

---

## 6. Migration manifest (ADR-8) — the authoritative checklist

Verified 100 % by `WS-V` V4 (AC-20); it is the precondition of the legacy repository's
deletion (ADR-7). Every row ends in exactly one of three states: **→ INFRA**, **→
EXPLORER**, or **DIES**.

### 6.1 → `dd-chain-infrastructure`

| Source | Destination | Note |
|---|---|---|
| `services/prd/{00_bootstrap,01_tf_state,04_peripherals,06_lambda}` | same paths | identical backend keys; `00_bootstrap` gains `github_repo` + the artifacts-publish role |
| `services/dev/{01_peripherals,02_lambda}`, `services/hml/04_peripherals` | same paths | identical backend keys |
| `services/modules/{cloudwatch_logs,dynamodb,lambda,s3}` | same paths | with their `required_providers` and lock files |
| `scripts/ci/**` (helpers, `changed_stacks.py`, `stack_map.json`, `publish_oidc_vars.sh`, `resolve_layer*.sh`, `tests/`) | same paths, **rewritten** | stack set re-pointed; `prd/03_iam` dropped; 4 security LOW guards folded in (I8) |
| `.github/workflows/{plan_on_pr,deploy_cloud_infra,destroy_cloud_infra,destroy_all_cloud_infra,drift_detection,scorecard}.yml` | same paths, **rewritten** | infra lane only |
| `docs/runbooks/00-bootstrap-apply.md`, `docs/governance/stale-branches-v0.5.0.md` | `docs/` | re-pointed at the new repo |
| **new:** the Databricks UC Terraform stack | `services/**` | authored + imported (I7) |

### 6.2 → the new `dd-chain-explorer`

| Source | Destination | Note |
|---|---|---|
| `specs/**` **in full**, `_archive/` included | `specs/**` | byte-identical, at C-DAY (AC-15) |
| `apps/dabs/**` (7 bundles) | same path | + `VERSION` axis at `0.6.0` |
| `apps/lambda/**` (2 handlers, requirements, lock) | same path | |
| `utils/**` (`dm-chain-utils`, 3 modules) | same path | |
| `tests/**` (dabs, lambda, utils suites + conftest) | same path | the `scripts/ci/tests` suite goes to INFRA instead |
| `docs/runbooks/{ci-security,lambda-layer}.md` | same path | re-pointed |
| `scripts/build_lambda_layer.sh` | same path | the build stays with the code (ADR-3) |
| `Makefile`, root `pyproject.toml` | rewritten lean | only what this tree needs |
| `README.md` | **new** | not the legacy one |
| **new:** the cross-repo contract doc | `docs/` | L3 |

### 6.3 DIES with the legacy repository

| Item | Reason |
|---|---|
| `.github/workflows/deploy_all_dm_applications.yml` | superseded — the app lane is rebuilt inside the explorer repo (X4) |
| `services/prd/03_iam` (directory + state key) | declares no resource since v0.5.0's `T-B.3a` |
| `apps/docker/` (if any residue survives) | capture-era; retired in v0.4.0/v0.5.0 |
| `scripts/{dev,hml}_dlt_integration_test.sh`, `scripts/empty_s3_bucket.sh`, `scripts/ci/empty_s3_and_ecr.sh` | re-homed only if a CI job actually calls them; otherwise dead — each row decided with evidence, never by assumption |
| `docs/runbooks/v0.5.0-live-cutover.md`, `docs/README.md` | release-scoped to v0.5.0 / superseded by the two new READMEs; the history is in `_archive/releases/v0.5.0/` |
| `.dockerignore` and any other container-era root file | no container compute in this platform |
| the legacy repository's git history | ADR-2 — reachable until the operator's deletion (ADR-7), never imported |

**Rule:** a row is never marked DIES by presumption. Each requires either a grep proving
no live caller, or an explicit operator ruling recorded in CLOSURE.

---

## 7. Execution model

- Definition and implementation run on `feature/0.6.0` in **each** repository — the
  same branch law, three times (`DADAIA.md` §4 Gitflow).
- Definition of this release is authored in the **legacy** repository (the only place
  `specs/` exists today) and is `Aprovado` there. The definition PR opens into that
  repo's `develop`.
- **Milestone (a):** SPEC + PLAN + TASKS all `Aprovado` → merge into `develop`,
  diff-based security review, push.
- **alpha-1 (V6):** WS-I, WS-X and WS-L implemented; `qa-engineer` review committed.
- **C-DAY (V5, O-6):** the specs handover. **After this instant the release lives in the
  new `dd-chain-explorer` repository** — that is where the remaining marker flips, the
  memory updates and `CLOSURE.md` are written, and where this release is archived.
- **rc-1 (V7):** the full trio APPROVED, in both repositories.
- **Ship (V8):** memory update → CLOSURE → archive **in the new explorer repo**, then
  `develop` → `main` PRs in both repos, CI watched to green.
- **Post-gate, operator-only (WS-D):** credential cleanup → operator validation → PUBLIC
  flip → legacy repository deletion.

---

## 8. Memory files affected at CLOSURE (do NOT write now)

Written in the **new** `dd-chain-explorer` repository, after C-DAY.

| Atom | Written when |
|---|---|
| `specs/memory/architecture.md` | WS-I and WS-L close — a new ADR records the three-repo boundary, the artifacts contract as the inter-repo seam, and the CI+Terraform-only law with its bootstrap exception; the layer map states which repository owns each layer |
| `specs/memory/product/aws-resources.md` | WS-I closes — the artifacts bucket moves from *declared-not-applied* to live; `prd/03_iam` leaves the stack table; the five OIDC roles and the repositories they trust; the Databricks UC objects become Terraform-managed |
| `specs/memory/product/cicd-pipeline.md` | WS-I and WS-X close — **two** control planes replace one: the infra lane and the explorer lane, with their workflow inventories, gates and role usage |
| `specs/memory/tech-stack.md` | WS-I and WS-X close — the repository topology, where each surface lives, and the artifact contract replacing the working-tree layer path |
| `specs/memory/product/medallion-pipelines.md`, `serving-layer.md` | WS-X closes **only if** the bundle inventory or deploy path statement changes |
| `specs/memory/quality-assurance.md` | WS-X and WS-I close — the pyramid now spans two repositories; which suite runs in which CI |
| `specs/memory/product/index.md` + `catalog.json` | only if a feature's rank changes or an atom is added/removed; the stale "CI cannot authenticate today" limit is corrected regardless |
| `specs/memory/product/capture-layer.md`, `data-catalog.md` | expected **no change** — the capture boundary and the UC object inventory are untouched by a topology move; a no-change statement with its reason is still recorded |

---

## 9. Dependencies & risks

| Risk | Mitigation |
|---|---|
| **Terraform state is the single point of no return.** A wrong backend key, a renamed resource address or a re-`init` against the wrong bucket destroys live infrastructure. | O-5 + AC-3: stacks move as content with **identical** backend keys and addresses; the only accepted proof is a fresh-clone `0 to add, 0 to change, 0 to destroy` on every stack. No `terraform apply` runs from the new repo before its own plan is clean. |
| **Databricks UC recreation would drop data access** for every catalog and external location. | ADR-5 is import-only, and O-4 makes it fail-closed: an object that cannot be imported escalates; it is never created. AC-7 accepts only `No changes`. |
| **The OIDC repoint is a hard flip** — during it, neither the old nor the new repo may be able to deploy for a moment. | The platform is parked by design (no data flowing, DLT triggers paused), so a deploy gap costs nothing. O-2 fixes the order and the operator applies the bootstrap in one step. |
| **The artifacts contract splits build from deploy across two repositories** — a stale or missing object makes a Lambda plan unresolvable. | Content-addressed keys, `resolve_layer` resolving by explicit `<sha256>`, and O-3's ordering. A missing object makes the step **skip with a warning** rather than silently plan against a stale artifact — the v0.5.0 behaviour, preserved. |
| **Specs could be written in two places at once** and silently diverge. | O-6/O-7: the handover is one atomic step with a frozen source and a named cutover instant; the legacy tree receives exactly one further commit, a tombstone. |
| **The new explorer repository is PUBLIC from birth** (ADR-9) — a single careless commit is world-readable immediately. | Nothing that is not public-grade is committed; AC-22's whole-tree secret scan gates both repos; secret **values** are only ever entered by the operator (O-10); the infrastructure repo stays PRIVATE until the operator validates. |
| **Deleting the legacy repository destroys the only copy of the git history.** | ADR-7 makes deletion an operator act behind three preconditions (manifest 100 %, both repos CI-green, operator validation), sequenced last by O-9. No agent may delete it or propose deleting it earlier. |
| **A file could be silently lost in the move** — the classic migration failure. | §6 is an exhaustive three-state manifest, verified row by row with evidence (AC-20); a DIES row needs a grep or an operator ruling, never a presumption. |
| **The dadaia-workspace multi-repo spec-context feature is in flight elsewhere.** | The structure assumes it (new explorer = main repo holding `specs/`, infrastructure = associated repo) but **nothing here depends on it landing**: if it does not, the new explorer is simply an ordinary spec context and the infrastructure repo has none. No task blocks on it. |
| **Two repositories double the governance surface** — protection, environments, reviewers, variables, all re-created by hand. | Every such step is an explicit `OPERATOR-ONLY` task row with its own acceptance check (AC-19, AC-21); none is assumed to have been inherited. |
| **Scope creep**: a migration is a tempting moment to "also fix" the stack tree, the dashboards, the DLT. | §3 refuses each by name. The only two absorbed items are the v0.5.0 deferrals that *are* this seam (`T-B.14`, `T-B.7`) and the four security LOW guards that travel with the code being rewritten. |

---

## 10. Decisions resolved (grill handoff `2026-08-23T203850Z-project-manager-grillme-3repo-segregation`)

The nine ADRs below are the operator-confirmed ground truth of this release. They are
quoted as ruled; where implementation detail was added by this SPEC it is marked.

- **ADR-1 — v0.5.0 closes first.** *"v0.5.0 closed first (DONE — shipped, archived, gate
  7.6/10); v0.6.0 starts from that green baseline."* No remediation work is re-litigated
  here.
- **ADR-2 — Fresh git, specs as content.** *"Fresh git start in BOTH new repos; specs
  migrate as CONTENT (full `specs/` tree incl. `_archive/`), never as git history."*
- **ADR-3 — The Lambda boundary.** *"Code + package/layer build stay in the new explorer;
  lambda Terraform moves to `dd-chain-infrastructure` consuming the artifact from the
  artifacts S3 bucket (`resolve_layer` contract)."* SPEC addition: the two handler zips
  follow the same contract as the layer, because `archive_file` from a working-tree path
  cannot survive the split.
- **ADR-4 — OIDC.** *"The 4 deploy roles re-trusted to `dd-chain-infrastructure`
  (bootstrap `github_repo` variable + re-apply); new narrow `artifacts-publish` role
  (PutObject on the artifacts bucket only) trusted to the new explorer repo."*
- **ADR-5 — Databricks split.** *"Databricks workspace infra (UC storage credentials,
  external locations, catalogs) becomes Terraform in the infrastructure repo via IMPORT,
  never recreation; DLT/workflows/dashboards stay DABs in the explorer."* SPEC addition
  (O-4): an object that cannot be imported escalates — it is never created.
- **ADR-6 — The new law.** *"NEW LAW in scoped `AGENTS.md` of both repos: infra resources
  are created ONLY via CI pipeline + Terraform, never CLI; documented exception
  `prd/00_bootstrap` (operator-only)."*
- **ADR-7 — Legacy deletion is an operator act.** *"Legacy repo `dd_chain_explorer`
  deleted ONLY after: migration manifest 100 % verified, both new repos CI-green,
  operator final validation. Deletion is an operator act."*
- **ADR-8 — The migration manifest.** *"To new explorer: `specs/`, `apps/dabs/`,
  `apps/lambda/`, `utils/`, `tests/`, `docs/runbooks/{ci-security,lambda-layer}.md`, lean
  pyproject/Makefile, new README. To infrastructure (rewritten, not blind-copied):
  `services/` stacks, `scripts/ci/`, infra workflows. Dies with legacy: old workflows,
  empty `apps/docker/`, dead code."* Expanded row by row in §6.
- **ADR-9 — Visibility.** *"Infrastructure PRIVATE until operator validates → then
  PUBLIC; new explorer PUBLIC from birth (everything public-grade, zero secrets)."*

**Absorbed from v0.5.0's intake (§2 I4, I5, I8).** `T-B.14`'s artifacts bucket and layer
rewire, `T-B.7`'s Terraform-path schedule disable, and four security LOW guards that
travel with the code being rewritten (boundary `sts:` regression pin,
`log_groups_describe_arn` single-statement pin, raw interpolation → environment binding,
preflight ARN masking). **Left in the backlog, named:** `terraform-single-stack-tree-per-env-tfvars`,
`capture-ecr-state-and-kms-ownership-transfer`, `rest-api-public-endpoint`,
`encryption-at-rest-posture-decision`, `s3-raw-lifecycle-intelligent-tiering`,
`dlt-ethereum-data-quality-enhancements`, `dashboards-analytics-enrichment`, alert/Genie
reinstatement, the `zizmor --offline` and `harden-runner` posture decisions, the
`DescribeLogGroups` prefix probe, and the rotate-or-accept ruling on the public Databricks
account UUID.
