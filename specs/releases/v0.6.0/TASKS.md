# TASKS — Release v0.6.0 — Three-repo segregation migration

> **Status:** Aprovado
> **Release ID:** v0.6.0
> **Owner:** product-engineer (authoring) → software-engineer / qa-engineer / code-reviewer / security-reviewer / coordinator / **operator** (execution, per task)
> **Depends on:** SPEC.md + PLAN.md v0.6.0 (`Aprovado`)
> **Marker contract:** `[ ]` OPEN → `[-]` IN PROGRESS → `[x]` DONE. Reserve with an isolated `chore(tasks): start <id>` commit **before** writing. Max one `[-]` per owner; the workstreams have disjoint write sets (by repository and tree), so WS-I, WS-X, WS-L and the closer may each hold one `[-]` in parallel. Flip to `[x]` only after the review boundary covering the task clears. All tasks below are `[ ]`.

**Write-set law.** WS-I writes only inside `dd-chain-infrastructure` (plus the Terraform
state keys and the live AWS resources this project already owns). WS-X writes only inside
the new `dd-chain-explorer` (plus the live Databricks `dev`/`hml` targets and objects under
the artifacts bucket's own prefixes). WS-L writes `AGENTS.md` in both new repos, the new
explorer's `docs/`, and `specs/constitution.md` in whichever repo is authoritative. WS-V
writes evidence and, after C-DAY, `specs/**` in the **new explorer repo only**. WS-D writes
nothing but GitHub repository settings and is **OPERATOR-ONLY**. No task writes the legacy
repository's tree except `T-V.5` (the tombstone). `AC-n` = SPEC §4; `O-n` = SPEC §5;
`K-n` = PLAN §2.

**OPERATOR-ONLY** marks a task no agent may execute: it holds a secret value, changes
repository settings or visibility, applies `prd/00_bootstrap`, or deletes something. An
agent may author its inputs and verify its outcome — never run it.

---

## WS-I — `dd-chain-infrastructure` (PRIVATE until validated)

- [ ] **T-I.1** — Create the repository skeleton on a **fresh git** (I1, ADR-2): `git init` in the empty target repo, with **no** remote of the legacy repository ever added; branches `main` → `develop` → `feature/0.6.0`; root `VERSION` = `0.6.0`; `.gitignore`; `pyproject.toml` carrying the ruff/mypy/pytest configuration the CI script suite needs; a new README naming this repository's single concern.
  - Owner: software-engineer · Write set: `dd-chain-infrastructure` repo root
  - Deps: — · AC-1, AC-14
  - Acceptance: `git log --format=%H | tail -1` is this migration's own initial commit; `git log --oneline | wc -l` counts only migration commits; no legacy sha is reachable; `cat VERSION` → `0.6.0`.

- [ ] **T-I.2** — **OPERATOR-ONLY.** Provision the `dd-chain-infrastructure` repository settings: visibility **PRIVATE**; branch protection on `main` (PR required + required status checks, no force-push, no deletion) and `develop` (no force-push, no deletion); environments `dev`, `hml`, `production` with the operator as required reviewer on `hml` and `production` and a deployment-branch policy of `develop` + `main`; the allowed-actions allowlist; all secret **values** entered by the operator (no agent reads or transcribes one, O-10).
  - Owner: **operator** · Write set: GitHub repository settings
  - Deps: T-I.1 · AC-19, AC-21
  - Acceptance: `gh api repos/{owner}/{repo}/branches/{main,develop}/protection` and `.../environments` return the described configuration; `gh repo view --json visibility` → `PRIVATE`.

- [ ] **T-I.3** — Move Terraform as content with **identical backend keys and resource addresses** (I2): the 7 surviving root stacks (`prd/{00_bootstrap,01_tf_state,04_peripherals,06_lambda}`, `dev/{01_peripherals,02_lambda}`, `hml/04_peripherals`) and the 4 modules (`cloudwatch_logs`, `dynamodb`, `lambda`, `s3`), with their committed `.terraform.lock.hcl` files and `required_providers`. **`prd/03_iam` is not copied** — it declares no resource.
  - Owner: software-engineer · Write set: `services/**` in `dd-chain-infrastructure`
  - Deps: T-I.1 · AC-2, AC-3
  - Acceptance: `terraform fmt -check -recursive` and `terraform validate` clean on every stack; a lock file per root stack; `services/prd/03_iam` absent; every `backend "s3"` key byte-identical to the legacy declaration.

- [ ] **T-I.4** — Rewrite `prd/06_lambda` and `dev/02_lambda` to the **artifact contract** (I3, ADR-3, K3): the layer and both handler zips arrive as `*_s3_key` + `*_sha256` variables resolved by `scripts/ci/resolve_layer.sh` against the bucket and key shape pinned by `T-L.3`. No `archive_file` over a working-tree path survives — the source tree lives in the other repository.
  - Owner: software-engineer · Write set: `services/prd/06_lambda/**`, `services/dev/02_lambda/**`, `scripts/ci/resolve_layer*.sh`
  - Deps: T-I.3, T-L.3 (contract pinned first) · AC-3, AC-11
  - Acceptance: `grep -rn 'filebase64sha256\|archive_file' services/` → 0; `terraform validate` clean; the resolve step skips **with a warning** when no object exists at the key, never plans against a stale artifact.

- [ ] **T-I.5** — Remove the `prd/03_iam` state key from the state bucket once `T-V.2` has proven every surviving stack plans clean without it (I2; v0.5.0 intake residual, folded).
  - Owner: software-engineer · Write set: the Terraform state bucket's key space
  - Deps: T-I.3, T-V.2 · AC-2
  - Acceptance: `aws s3api list-objects-v2 --bucket <state-bucket>` shows the surviving stack keys plus `capture/ecr` (owned by `dd-chain-capture`, documented not moved) and **no** `prd/03_iam` key.

- [ ] **T-I.6** — Author the bootstrap repoint (I6, ADR-4): a `github_repo` variable feeding the four deploy roles' trust `sub` conditions (`repo:<owner>/dd-chain-infrastructure:environment:<env>` per deploy role; `pull_request` + `refs/heads/{develop,main}` for the read-only role), plus a new `…-gha-artifacts-publish` role trusted to `repo:<owner>/dd-chain-explorer:…` whose **entire** policy is `s3:PutObject`, `s3:PutObjectTagging`, `s3:AbortMultipartUpload` on `<artifacts-bucket>/*` and `s3:ListBucket` on the bucket, carrying the project permissions boundary like every other project role.
  - Owner: software-engineer · Write set: `services/prd/00_bootstrap/**`
  - Deps: T-I.3 · AC-6, AC-6b
  - Acceptance: no managed-policy attachment, no `iam:*` on `"*"`, no widened `sts:` allowance; `terraform validate`/`fmt -check` clean; `terraform plan` shows only the trust-policy update and the one new role.

- [ ] **T-I.7** — Security verdict on the bootstrap delta **before** any apply (O-2).
  - Owner: security-reviewer · Write set: `.dadaia/handoff/dd-chain-explorer/` (handoff only)
  - Deps: T-I.6 · AC-6, AC-6b
  - Acceptance: an APPROVED handoff naming the commit sha, confirming the repointed `sub` conditions, the artifacts-publish role's minimality, the retained self-mutation `Deny` and the boundary on the new role.

- [ ] **T-I.8** — **OPERATOR-ONLY.** Apply `services/prd/00_bootstrap` with operator credentials — the sole documented exception to ADR-6's law, and the only stack CI may never apply (O-2).
  - Owner: **operator** · Write set: live AWS IAM (5 roles' trust and policy) + the `prd/bootstrap` state key
  - Deps: T-I.7 · AC-6
  - Acceptance: apply summary; post-apply `terraform plan` → `No changes`; `aws iam get-role` on all five roles shows the new trust; `simulate-principal-policy` on `…-gha-artifacts-publish`: `s3:PutObject` on `<artifacts-bucket>/*` → `allowed`, and `s3:GetObject` on the state bucket / `lambda:UpdateFunctionCode` / `iam:PassRole` → denied.

- [ ] **T-I.9** — Publish the deploy-role variables in the new repository: run `scripts/ci/publish_oidc_vars.sh` against the applied bootstrap outputs to set `AWS_DEPLOY_ROLE_{DEV,HML,PRD,READONLY}`, and confirm the fail-fast preflight guards every role-assuming job. The **values** are role ARNs, published by the operator-run script; no static key is ever created (O-10).
  - Owner: software-engineer (script, preflight, test) · **operator** (execution against live outputs) · Write set: `scripts/ci/publish_oidc_vars.sh`, `scripts/ci/tests/**`, repository variables
  - Deps: T-I.8 · AC-8, AC-9, AC-19
  - Acceptance: `gh variable list` shows the four names non-empty; a deliberately emptied variable fails the job **at the preflight step** with an explicit message; the preflight prints no unmasked role ARN.

- [ ] **T-I.10** — Land the artifacts bucket and both absorbed v0.5.0 deferrals in one apply (I4, I5): `<artifacts-bucket>` declared in `prd/04_peripherals` (versioned, private, all public-access blocks on, encrypted; `dev` consumes a `dev/` prefix), the Lambda log-group imports, and the PRD contracts-ingestion schedule's `DISABLED` state declared in Terraform.
  - Owner: software-engineer (author) · **operator-gated apply** (creates a productive PRD resource) · Write set: `services/prd/04_peripherals/**`, `services/prd/06_lambda/**`, `services/dev/02_lambda/**`; live AWS (bucket, log-group imports, schedule state)
  - Deps: T-I.3, T-I.9 · AC-4, AC-5 · Absorbs: v0.5.0 `T-B.14`, `T-B.7`
  - Acceptance: `head-bucket` 200; `get-bucket-versioning` → `Enabled`; `get-public-access-block` → four `true`; `aws scheduler get-schedule` → `State: DISABLED` **and** declared so; post-apply plan clean on all three stacks.

- [ ] **T-I.11** — Inventory and declare the Databricks workspace infrastructure (I7, ADR-5, K4): list every existing Unity Catalog **storage credential**, **external location** and **catalog** (`databricks storage-credentials list`, `external-locations list`, `catalogs list`), then author a Terraform stack declaring exactly those objects — no more, no fewer. DLT pipelines, workflows, jobs and dashboards are **not** declared; they stay DABs.
  - Owner: software-engineer · Write set: the new Databricks UC stack under `services/**`
  - Deps: T-I.3 · AC-7
  - Acceptance: the committed inventory lists every object with its id; the stack declares one resource per inventoried object; `terraform validate` clean; **no `create` has been run** at this point.

- [ ] **T-I.12** — Adopt every inventoried object with `terraform import`, one at a time, re-planning after each (O-4). **Fail-closed:** an object that cannot be imported stops WS-I and escalates to the operator with the partial state recorded; the fallback is to remove the resource block, **never** to create the object.
  - Owner: software-engineer · **operator-gated** (writes the UC stack's state) · Write set: the UC stack's Terraform state
  - Deps: T-I.11 · AC-7
  - Acceptance: post-import `terraform plan` → **`No changes`**; `databricks storage-credentials get` / `external-locations get` return the **same ids** that the `T-I.11` inventory recorded — nothing was recreated.

- [ ] **T-I.13** — Migrate and re-point `scripts/ci/**` and its pytest suite (I8, K6): helpers, `changed_stacks.py`, `stack_map.json` (surviving stacks only — `prd/03_iam` dropped), `publish_oidc_vars.sh`, `resolve_layer*.sh`, and `scripts/ci/tests/`. Add the two new guard tests: one pinning the permissions boundary's `sts:` allowances against silent widening, one pinning `log_groups_describe_arn` to its single statement.
  - Owner: software-engineer · Write set: `scripts/ci/**` in `dd-chain-infrastructure`
  - Deps: T-I.3 · AC-9 · Absorbs: 2 of the 4 v0.5.0 security LOW residuals
  - Acceptance: `pytest scripts/ci/tests -p no:cacheprovider` green **and** executed by CI; a test asserts `stack_map.json`'s stack set equals the directories on disk; a test asserts `destroy_all`'s stack set equals the map's survivors.

- [ ] **T-I.14** — Re-author the six infrastructure workflows (I8) — plan-on-PR, deploy, destroy, destroy-all, drift detection, Scorecard — keeping the v0.5.0 posture (SHA-pinned actions under the allowlist, `persist-credentials: false`, runner hardening, per-environment `concurrency`, `-lock=false` on the read-only plan path, `actionlint` + `zizmor` + `terraform fmt/validate` gates, the OIDC preflight on every role-assuming job). **No application-deploy workflow travels.** Fold in the remaining two security LOW residuals: the raw interpolation in the deploy workflow becomes an environment binding, and the preflight masks the role ARN.
  - Owner: software-engineer · Write set: `.github/workflows/**` in `dd-chain-infrastructure`
  - Deps: T-I.13 · AC-8, AC-24 · Absorbs: 2 of the 4 v0.5.0 security LOW residuals
  - Acceptance: `gh workflow list` shows the infrastructure lane only; `actionlint` and `zizmor` clean; `grep` finds no raw interpolation into a privileged step; drift detection present on the default branch and **enabled** (its first cron recorded as pending, never claimed as evidence).

---

## WS-X — the new `dd-chain-explorer` (PUBLIC from birth)

- [ ] **T-X.1** — Create the repository skeleton on a **fresh git** (X1, ADR-2): `git init`, no legacy remote ever added; branches `main` → `develop` → `feature/0.6.0`; a lean root `pyproject.toml` (ruff + mypy + pytest scoped to this tree); a Makefile of thin wrappers over the scripts CI actually runs; `.gitignore`; and a **new** README describing the spec-context main repo and its two surfaces.
  - Owner: software-engineer · Write set: new `dd-chain-explorer` repo root
  - Deps: — · AC-1, AC-10
  - Acceptance: fresh history (no legacy sha reachable); `make -n <target>` resolves for every target the README cites; no `services/` directory exists.

- [ ] **T-X.2** — **OPERATOR-ONLY.** Provision the new `dd-chain-explorer` repository settings: visibility **PUBLIC** from birth (ADR-9); branch protection on `main` and `develop` mirroring the infrastructure repo; environments `dev`, `hml`, `production` with the operator as required reviewer on `hml` and `production`; the allowed-actions allowlist; all secret **values** (Databricks host/token and any environment secret) entered by the operator (O-10).
  - Owner: **operator** · Write set: GitHub repository settings
  - Deps: T-X.1 · AC-19, AC-22
  - Acceptance: `gh repo view --json visibility` → `PUBLIC`; protection and environments match the described configuration; `gh secret list` shows names only, and no agent has read a value.

- [ ] **T-X.3** — Migrate the application content as content (X2, X7): `apps/dabs/` (7 bundles), `apps/lambda/` (both handlers + requirements + the hash-checked lock), `utils/` (the three-module `dm-chain-utils`), `docs/runbooks/{ci-security,lambda-layer}.md`, `scripts/build_lambda_layer.sh`. Set the version axis to `0.6.0`: root `VERSION`, every `apps/dabs/*/VERSION`, the library distribution version and its `__init__.py` declaration (the infrastructure repo's `VERSION` is `T-I.1`'s).
  - Owner: software-engineer · Write set: `apps/**`, `utils/**`, `docs/runbooks/**`, `scripts/build_lambda_layer.sh`, `VERSION` in the new explorer repo
  - Deps: T-X.1 · AC-10, AC-14
  - Acceptance: every manifest row of SPEC §6.2 present; `cat VERSION` and `cat apps/dabs/*/VERSION | sort -u` → `0.6.0`, matching the infrastructure repo.

- [ ] **T-X.4** — Migrate the test tree (X2, K6, O-8): `tests/` — the dabs, lambda and utils suites plus `conftest.py` and `tests/README.md`. The `scripts/ci/tests` suite travels to WS-I instead; the **union** of the two repositories' suites must equal the set that was green at v0.5.0. Any test dropped in the move requires a `qa-engineer` verdict.
  - Owner: software-engineer · Write set: `tests/**` in the new explorer repo
  - Deps: T-X.3 · AC-12
  - Acceptance: `pytest -p no:cacheprovider` green locally and in CI; every test declares intent and size; a `qa-engineer` verdict handoff exists for any subtraction, or the count reconciles exactly with v0.5.0's.

- [ ] **T-X.5** — Implement the **producer** half of the artifact seam (X3, ADR-3, K3): CI builds the layer (`pip install --require-hashes -r requirements.lock -t build/` for third-party deps **plus** `pip install ./utils -t build/ --no-deps` — the path install is what closes dependency confusion) and both handler zips, uploads each to its content-addressed key under the bucket and prefix shape pinned by `T-L.3`, assuming **only** `…-gha-artifacts-publish`, and emits each `<sha256>` as a run output the infrastructure repo's resolver can name.
  - Owner: software-engineer · Write set: `.github/workflows/**`, `scripts/build_lambda_layer.sh` in the new explorer repo; objects under the artifacts bucket's layer/handler prefixes
  - Deps: T-X.3, T-I.8 (the role must exist), T-L.3 · AC-11
  - Acceptance: `aws s3api list-objects-v2` shows the layer and both handler zips at content-addressed keys; the job log shows the artifacts-publish role and no other; `grep` finds no public-index pin of the library.

- [ ] **T-X.6** — Build the explorer CI (X4): the quality gate (`ruff format --check`, `ruff check`, `mypy`, `pytest -p no:cacheprovider`, `pip-audit -r` over the lock), the publish job of `T-X.5`, `databricks bundle validate` per bundle per target, and the DABs deploy lane behind the informed environment gate. `actionlint` + `zizmor` clean, every action SHA-pinned, `persist-credentials: false`, runner hardening. **No Terraform workflow, and no role beyond `artifacts-publish`.**
  - Owner: software-engineer · Write set: `.github/workflows/**` in the new explorer repo
  - Deps: T-X.4, T-X.5 · AC-12, AC-13, AC-6b
  - Acceptance: all gate jobs exit 0 in CI; `gh workflow list` contains no infrastructure workflow; `grep` finds no `AWS_DEPLOY_ROLE_*` reference in this repository.

- [ ] **T-X.7** — Validate and deploy the bundles from the new repository (X5): all 7 validate in `dev` and `hml`; the `prod` target stays guarded (host variable with no default); deploy `dev` and `hml`; then diff every deployed pipeline's exported notebook against its file in the **new** repo.
  - Owner: software-engineer · Write set: the live Databricks `dev` and `hml` targets
  - Deps: T-X.6 · AC-13
  - Acceptance: `databricks bundle validate -t dev` and `-t hml` exit 0 per bundle; `-t prod` with the host unset exits **non-zero**; notebook export `diff` exit 0 per deployed pipeline; no orphan job or stale `.bundle` root left behind.

---

## WS-L — laws, `AGENTS.md`, cross-repo documentation

- [ ] **T-L.1** — Author the scoped `AGENTS.md` of `dd-chain-infrastructure` carrying the new law (L1, ADR-6), stated normatively: infrastructure resources are created, changed and destroyed **only** by the CI pipeline applying Terraform — never by a console click, never by an ad-hoc CLI mutation. The **sole** documented exception is `services/prd/00_bootstrap`, applied by the operator, never by CI, with its reason recorded (the bootstrap paradox). A CLI mutation outside that exception is a defect to register, not a shortcut.
  - Owner: ai-engineer (scoped `AGENTS.md` is AI-surface) · Write set: `AGENTS.md` in `dd-chain-infrastructure`
  - Deps: T-I.1 · AC-16
  - Acceptance: the law and its single exception are stated once, unambiguously, with the bootstrap path named literally.

- [ ] **T-L.2** — Author the scoped `AGENTS.md` of the new `dd-chain-explorer` (L2): this repository declares **no** infrastructure — Terraform belongs to `dd-chain-infrastructure`, capture to `dd-chain-capture`; it is the **main repo of the spec context**, so `specs/` is authoritative here; it is **PUBLIC**, so nothing that is not public-grade may be committed.
  - Owner: ai-engineer · Write set: `AGENTS.md` in the new `dd-chain-explorer`
  - Deps: T-X.1 · AC-16
  - Acceptance: all three statements present; the boundary to the other two repositories named explicitly.

- [ ] **T-L.3** — Author the cross-repo contract document (L3, K3) in the new explorer's `docs/`, **before** `T-I.4` and `T-X.5` are written: the artifacts bucket, prefixes and content-addressed key shape; who publishes and who resolves; the five-role OIDC map with the repository each trusts and what each may do; the Databricks split (workspace infra = Terraform-by-import in the infrastructure repo, DLT/workflows/dashboards = DABs here); and the three-repo boundary diagram. Re-point every migrated runbook at its new repository.
  - Owner: software-engineer · Write set: `docs/**` in the new `dd-chain-explorer`
  - Deps: T-X.1 · AC-17
  - Acceptance: the key shape is stated once and is the source both implementations cite; `grep` finds no stale repository name in any migrated runbook; no account id, host or personal identifier appears (the repository is public).

- [ ] **T-L.4** — Amend `specs/constitution.md` to the three-repo topology **in the legacy repository, before C-DAY** (L4, K5), so it travels already correct: the repository boundary, the two laws of `T-L.1`/`T-L.2`, and the statement that `specs/` is authoritative in the new explorer repository. **Requires explicit operator confirmation** before writing.
  - Owner: product-engineer · Write set: `specs/constitution.md` (legacy repo)
  - Deps: T-L.1, T-L.2 · **Must land before T-V.4 (O-7)** · AC-18
  - Acceptance: the three statements present; `dadaia specs doctor` clean; the file is included byte-identically in `T-V.4`'s handover.

---

## WS-V — validation, cutover, release gates

- [ ] **T-V.1** — Prove both control planes: CI green on `feature/0.6.0` in **both** new repositories, and the union of their pytest suites equals the set that was green at v0.5.0 (K6).
  - Owner: qa-engineer · Write set: evidence only
  - Deps: T-I.14, T-X.6, T-I.2, T-X.2 · AC-12, AC-19
  - Acceptance: both repos' check sets green; a committed suite-reconciliation table; any subtraction carries a `qa-engineer` verdict.

- [ ] **T-V.2** — Prove the infrastructure equality: every stack plans `0 to add, 0 to change, 0 to destroy` from a **fresh clone** of `dd-chain-infrastructure` under OIDC, including the imported UC stack and the newly applied artifacts bucket, with the Lambda stacks resolving real artifacts published by `T-X.5` (never a hand-uploaded object).
  - Owner: qa-engineer · Write set: evidence only
  - Deps: T-I.10, T-I.12, T-X.5 · AC-3, AC-7
  - Acceptance: a per-stack plan summary of `0/0/0`. **A non-zero `add` count is a stop-the-line event** — it is escalated, never reconciled by applying.

- [ ] **T-V.3** — Prove the Databricks and secret-hygiene equalities: the imported UC credentials and external locations validate; both hml buckets answer `head-bucket`; every bundle validates and deployed state equals the new explorer repo; and a whole-tree secret scan (denylist + `gitleaks`-class) is clean in **both** new repositories.
  - Owner: qa-engineer + security-reviewer · Write set: evidence only
  - Deps: T-X.7, T-I.12 · AC-13, AC-22
  - Acceptance: validate PASS on every credential and location; bundle validate exit 0; export diff exit 0; **zero** secret-scan findings in either repo.

- [ ] **T-V.4** — **C-DAY — the cutover (O-6, O-7, K5).** With both repos CI-green (`T-V.1`), the equalities proven (`T-V.2`, `T-V.3`) and the manifest verified (`T-V.7` rows for everything migrated so far), copy the **entire** `specs/` tree — `constitution.md`, `memory/**`, `releases/**` (this release included), `backlog/**`, `bugs/**`, `audits/**` and `_archive/**` in full — into the new `dd-chain-explorer` repository and commit. **This is a critical section: no other task may write `specs/**` in either repository while it runs.** From this commit the legacy `specs/` tree is **FROZEN** and every remaining SDD write of this release happens in the new explorer repository.
  - Owner: product-engineer · Write set: `specs/**` in the new explorer repo (read-only on the legacy tree)
  - Deps: T-V.1, T-V.2, T-V.3, T-L.4 · AC-15, AC-23
  - Acceptance: `diff -r` between the two `specs/` trees is **empty**; `dadaia specs doctor` in the new repo → 0 errors; the legacy tree is untouched by the operation.

- [ ] **T-V.5** — Write the legacy repository's single remaining commit: a tombstone README pointing at both successors and stating that this tree is frozen and scheduled for operator deletion. Nothing else is ever committed there again.
  - Owner: product-engineer · Write set: the legacy repository's `README.md` (one commit)
  - Deps: T-V.4 · AC-21
  - Acceptance: `git -C <legacy-clone> log -1` is the tombstone; no `specs/` path is touched by it.

- [ ] **T-V.6** — **alpha-1:** WS-I, WS-X and WS-L implemented; `qa-engineer` review committed to both branches.
  - Owner: qa-engineer · Write set: `specs/releases/v0.6.0/**` in the **new explorer repo** (post-C-DAY)
  - Deps: T-V.5 · AC-19
  - Acceptance: an APPROVED qa handoff naming the head sha of each repository.

- [ ] **T-V.7** — Verify the **migration manifest** (SPEC §6) row by row to 100 % (V4, ADR-7): every row marked *arrived at its destination with evidence* or *deliberately dead with a reason*. A DIES row needs a grep proving no live caller **or** an explicit operator ruling — never a presumption. The verified checklist is committed as CLOSURE evidence and is a precondition of both the ship gate and the operator's deletion.
  - Owner: product-engineer · Write set: `specs/releases/v0.6.0/**` in the new explorer repo
  - Deps: T-V.6 · AC-20
  - Acceptance: **zero** unresolved rows; each DIES row carries its grep output or the operator ruling that decided it.

- [ ] **T-V.8** — **rc-1:** the full trio — `qa-engineer`, `code-reviewer` (six-axis on the delta), `security-reviewer` (diff-based) — APPROVED, in **both** repositories, on the same head sha per repo.
  - Owner: qa-engineer, code-reviewer, security-reviewer · Write set: handoffs only
  - Deps: T-V.7 · AC-19
  - Acceptance: three APPROVED handoffs per repository, each naming the sha it covers.

- [ ] **T-V.9** — **Ship (V8):** in the new explorer repository — memory update (SPEC §8) → `CLOSURE.md` → artifact GC sweep → archive; then open and merge `develop` → `main` in **both** repositories, watching CI to green after every push and PR.
  - Owner: product-engineer (memory, CLOSURE, archive) + coordinator (PRs) · Write set: `specs/memory/**` and `specs/releases/v0.6.0/**` in the new explorer repo
  - Deps: T-V.8 · AC-19..AC-24 · Ship gate: SPEC §4
  - Acceptance: memory atoms updated with a no-change reason recorded for each untouched atom; `CLOSURE.md` complete; both `main` PRs merged with every check green; the release archived to `specs/_archive/releases/v0.6.0/` and `ACTIVE.md` repointed.

---

## WS-D — legacy decommission (**OPERATOR-ONLY**, post-gate)

> No task in this workstream is agent-executable (O-9). An agent about to run one of these
> has misread the release. Agents may verify the outcome and record it in CLOSURE.

- [ ] **T-D.1** — **OPERATOR-ONLY.** Clean the legacy repository's credential surface: remove its variables, secrets and environments, so nothing there can deploy anything.
  - Owner: **operator** · Write set: `dd_chain_explorer` repository settings
  - Deps: T-V.9 · AC-21
  - Acceptance: `gh api` shows no variable, secret or environment remaining on the legacy repository.

- [ ] **T-D.2** — **OPERATOR-ONLY.** Flip `dd-chain-infrastructure` **PRIVATE → PUBLIC** (ADR-9) after the operator's own validation, and only once a fresh whole-tree secret scan is clean (the tree changed since `T-V.3`).
  - Owner: **operator** · Write set: `dd-chain-infrastructure` visibility
  - Deps: T-D.1, a re-run of AC-22 · AC-22
  - Acceptance: the re-run scan reports zero findings; `gh repo view --json visibility` → `PUBLIC`.

- [ ] **T-D.3** — **OPERATOR-ONLY.** Delete the legacy repository `dd_chain_explorer` (ADR-7). Permitted only after: the migration manifest 100 % verified (`T-V.7`), both new repositories CI-green (`T-V.1`, `T-V.9`), and the operator's explicit final validation. **This destroys the only copy of the legacy git history and has no rollback.**
  - Owner: **operator** · Write set: the legacy repository's existence
  - Deps: T-D.2 and the operator's explicit final validation · AC-20, AC-21
  - Acceptance: the repository no longer resolves; the act is recorded in CLOSURE as an operator act with its date and the three preconditions it satisfied.
