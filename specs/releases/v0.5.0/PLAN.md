# PLAN — Release v0.5.0 — Remediation: clean restart of infra, CI and Databricks artifacts

> **Status:** Aprovado
> **Release ID:** v0.5.0
> **Owner:** product-engineer
> **Depends on:** SPEC.md v0.5.0 (`Aprovado`)
> **Branch:** `feature/0.5.0` (cut from `develop`) — `dadaia-gitflow`

This release is a **remediation**, not a feature: it deletes, rewires and re-applies until
the declared platform equals the live platform. Five workstreams (SPEC §2) have file-level
disjoint write sets — one ordered seam, K3 — run in parallel, and couple only in the ten ways
listed in §2. Every live mutation is operator-gated with a rollback path in §9.

## 1. Strategy

1. **Code first, live second, per workstream**, each landing reviewed commits on
   `feature/0.5.0` before its operator-gated live half. One exception: the `prd/00_bootstrap`
   apply (D14), run locally by the coordinator because CI cannot authenticate until it
   exists — and which CI must never run afterwards.
2. **Deletion is the main mechanic.** Capture-era IaC, code, tests, bundles and docs are
   removed, not archived — git history is the archive (D3/D4). Every deletion has an AC that
   proves absence *and* a sibling AC that proves the survivors survived.
3. **Truthfulness is the acceptance shape.** A stack is done at 0 diff from a **fresh clone**
   (AC-10); a bundle when an exported notebook diffs clean against the repo (AC-18); CI when
   `plan_on_pr` is green under OIDC (AC-4).
4. **Root cause over symptom.** Two structural moves replace the two workarounds the
   architecture review rejected — the CI roles leave the CI-applied stack (D14), the layer
   artifact leaves the module tree (D15). Neither is re-litigated during implementation.
5. **The re-audit is the ship gate.** Score ≥ 7, no dimension < 5 (SPEC §4).

**Layers affected:** Terraform IaC (`services/**`), CI (`.github/workflows/**`,
`scripts/ci/**`), Databricks bundles (`apps/dabs/**`), application/library code
(`apps/lambda/**`, `utils/**`, `scripts/**`), repository governance (GitHub settings),
and the SDD tree (`specs/**`).

## 2. Cross-workstream couplings (the only ones)

| # | Coupling | Resolution |
|---|---|---|
| K1 | O-2 — no plan/apply may run while the two April state locks are held | `T-B.1` force-unlock is the first live task of the release; `T-A.3`, `T-B.13` and every plan depend on it |
| K2 | O-1 — CI cannot authenticate until the four roles exist, and they must not live in a CI-applied stack (D14) | `T-A.1` authors `prd/00_bootstrap` → `T-A.2` security verdict → `T-A.3` coordinator-local apply → `T-A.4` `publish_oidc_vars.sh` + variables → **then** `T-B.3a` removes `oidc.tf` from `prd/03_iam` and applies it |
| K3 | O-4 — **the one ordered-not-disjoint seam**: `utils/pyproject.toml` and `utils/src/dm_chain_utils/__init__.py` are wholly WS-D's, but their version value comes from WS-A's axis | `T-A.9` (`VERSION`, `apps/dabs/*/VERSION`, `deploy_all.sh`) lands **before** `T-D.7` sets the library declarations to `0.5.0`, and before the first WS-C edit (`T-C.1`) |
| K4 | O-8 — the `main` cut-over has a fixed 9-step sequence | `T-A.7` lands the `main` trigger; `T-A.11`/`T-R.3` execute steps (3)–(9); protection (`T-A.10`) can only be set **after** the first `plan_on_pr` run on the PR names the check |
| K5 | HML bucket names + UC roles are shared between Terraform and the bundles | SPEC §2.2 B2 **pins the names** as the single source: `T-B.4` declares buckets + `dm-databricks-hml-s3-role`, `T-C.3` aligns bundle variables to them, `T-C.7` creates the storage credential + external location, `T-C.5` validates `hml` before `T-B.8`..`T-B.10` assert the destruction set |
| K6 | The Lambda layer crosses three workstreams (D15) | `T-D.4` writes `scripts/build_lambda_layer.sh` + `requirements.lock`; `T-B.14` creates `dm-chain-explorer-artifacts` and rewires `prd/06_lambda`/`dev/02_lambda` to `layer_s3_key`/`layer_sha256` + `archive_file`; `T-A.7` wires build → upload → `-var` pass-through. Order: `T-D.4` → `T-B.14` → `T-A.7`; no plan consuming the variables runs before an object exists at the key (O-1c) |
| K7 | O-7 — coverage must never dip to zero | `T-D.1` (live-surface pyramid) → `T-D.2` (`qa-engineer` deletion/demotion verdict) → `T-D.3` (deletions) |
| K8 | O-10 — audits archive only once every finding has evidence | `T-E.8` runs last in CLOSURE, after `T-E.6`'s disposition rows all carry evidence |
| K9 | O-1b — a remote-state alias must not outlive its state key | `T-B.3` removes the `prd/vpc` alias (and every consumer) and applies, **before** `T-B.11` deletes the `prd/vpc` state key |
| K10 | One Terraform stack, one applier | `prd/03_iam` is wholly WS-B's (D14); `prd/00_bootstrap` is wholly WS-A's and is applied only by the coordinator. No stack appears in two write sets |

Everything else is parallel: WS-A owns `.github/**` + `scripts/ci/**` + `prd/00_bootstrap`,
WS-B owns the rest of `services/**`, WS-C owns `apps/dabs/**` minus the carve-out, WS-D owns
application/library/docs/tests, WS-E owns `specs/**`.

## 3. WS-A — CI authentication, workflow purge, governance, version axis

**Approach.**

- **Bootstrap stack (`T-A.1`, D14).** `services/prd/00_bootstrap` — backend key
  `prd/bootstrap`, applied only by the coordinator, never by CI — declares the OIDC provider
  reference and four roles (`…-gha-deploy-{dev,hml,prd}`, `…-gha-readonly-plan`). Each is an
  explicit statement list (never a managed-policy attachment): prefix-scoped allows, an
  explicit `Deny` on `iam:*` against `arn:aws:iam::*:role/dm-chain-explorer-gha-*` and the
  user-credential verbs, and a `sub` pinned to `…:environment:<env>` (deploy) or
  `pull_request` + `refs/heads/{develop,main}` (read-only). The read-only role gets **no**
  lock-table write — the plan path passes `-lock=false` (F-04). AC-2/AC-2b/AC-4b are then
  decidable from `terraform show -json`, `get-role-policy` and `simulate-principal-policy`.
- **Bootstrap apply + publish (`T-A.3`, `T-A.4`, `T-A.5`).** Coordinator-local `apply` on
  `00_bootstrap` after the locks are released (K1) and its lock file is committed (O-5) — the
  only apply outside CI, and the only stack CI may never apply. Bootstrap is code, not tribal
  knowledge: `scripts/ci/publish_oidc_vars.sh` reads the outputs and `gh variable set`s the
  four names; a preflight step in every role-assuming workflow fails fast on an empty variable
  (asserted by a `scripts/ci/tests` case); a `docs/` runbook records the one-time apply. Then
  the static key pair and capture-era secrets are deleted and the CI user's 2025 key is
  deactivated, not deleted, so reactivation stays a rollback path.
- **Workflow purge (`T-A.6`).** `deploy_all_dm_applications.yml` becomes a two-job graph:
  Lambda deploy + DABs deploy, both behind the existing informed gate. `hml_provision.sh` /
  `hml_teardown.sh` shrink to the minimal HML lane WS-B keeps; the tombstoned
  `hml_integration_test_optimized.sh` gate call goes (WS-D deletes the file itself).
- **Safety batch (`T-A.7`, `T-A.8`).** Per-environment `concurrency:` shared by an
  environment's deploy and destroy workflows; `plan_on_pr` on PRs into both long-lived
  branches, running `scripts/ci/tests`, `utils/tests`, the repo-level `tests/` tree,
  `ruff format --check` + `ruff check` + `mypy` jobs, `pip-audit -r` over the lock file, the
  layer build+upload (K6) and per-stack `terraform plan -lock=false` (F-04, flag pinned by a
  test); `destroy_all` covering every live stack, asserted equal to `stack_map.json`'s
  survivors; `TF_VERSION` single-sourced with an exact `required_version`; actionlint pinned
  by version + checksum; `auto-bump-version.yml` and every `hml-apps` reference deleted;
  `stack_map.json` the single source the four hard-coded lists now read.
- **Version axis (`T-A.9`).** `VERSION` → `0.5.0`, the 15 bundle `VERSION` files aligned, the
  tag-skip removed from `deploy_all.sh`, `check_prd_version.sh` reading `VERSION`. The
  library declarations are WS-D's `T-D.7`, ordered after this (K3). Tag `v0.5.0` at ship.
- **Governance (`T-A.10`, `T-A.11`).** Coordinator `gh` actions inside O-8's 9-step cut-over:
  rename `master`→`main`, PR `develop`→`main`, take the required-check name from that PR's
  **first** `plan_on_pr` run, set protection, merge with a **merge commit** (never squash —
  `master` carries 4 unique commits), reconcile `main`→`develop`, then verify
  `drift_detection.yml` present and enabled on the default branch. Stale branches are listed
  as a committed artifact; none is deleted.

**Verification.** `actionlint`; `pytest scripts/ci/tests utils/tests -p no:cacheprovider`;
`gh variable/secret list`; `terraform show -json` prefix assertion +
`simulate-principal-policy` negatives per role; `aws iam list-access-keys`; `gh api
…/branches/{main,develop}/protection`; `gh repo view --json defaultBranchRef`;
`gh workflow view drift_detection`; a real `plan_on_pr` run on a PR into `main` from a fresh
clone. ACs: AC-1..AC-9 (incl. AC-2b, AC-3b, AC-4b, AC-7b).

## 4. WS-B — Terraform purge, HML reduction, live AWS cleanup

**Approach.**

- **Unlock first (`T-B.1`).** `terraform force-unlock <lock-id>` on both stuck stacks after
  confirming no workflow run is in flight (`gh run list --status in_progress`). Nothing
  else in WS-B may plan before this completes.
- **Stack deletion (`T-B.2`).** Remove the 12 capture-era / never-applied stack directories
  and the `ecs` + `vpc` modules wholesale. Because these stacks are 0-resource or never
  applied, deletion is a file operation plus a state-key removal (`T-B.11`) — not a destroy.
- **`prd/03_iam`, one owner (`T-B.3`, `T-B.3a`, D14).** The whole stack is WS-B's. `T-B.3`
  deletes the firehose branch of `modules/cloudwatch_logs` (and its fragile `[0]` index), the
  capture grants in `modules/iam` and `prd/03_iam/iam.tf`, the E2 cross-account/cluster role
  set (dead since the PRD workspace was destroyed 2026-04-11 — the load-bearing UC credential
  is `dm-databricks-dev-s3-role`, not these), the `databricks_account_uuid` **default** (the
  variable stays; a public repo carries no account identifier), the `kinesis_sqs` and
  `prd/vpc` remote-state aliases (K9 — applied before `T-B.11` deletes those keys), the six
  unused variables and the ignored `prevent_destroy` in `modules/s3`. `T-B.3a` then removes
  `oidc.tf` — one plan/apply event with the purge, once `00_bootstrap` holds the roles (K2).
- **HML reduction (`T-B.4`, `T-B.12`).** SPEC §2.2 B2 pins the names: `hml/04_peripherals`
  keeps `dm-chain-explorer-hml-raw-data` + `dm-chain-explorer-hml-lakehouse` and declares
  `dm-databricks-hml-s3-role`; `dev/01_peripherals` **imports** the live
  `dm-databricks-dev-s3-role`. One role per environment, each granting only its own buckets.
  Every other HML stack is deleted.
- **Artifact store and layer inputs (`T-B.14`, D15).** `dm-chain-explorer-artifacts`
  (versioned, private, block-public-access) is created in `prd/04_peripherals`; dev shares it
  under a `dev/` prefix. `prd/06_lambda` and `dev/02_lambda` stop calling `filebase64sha256`
  on a working-tree path: the layer arrives as `layer_s3_key` + `layer_sha256` variables, the
  handler zips as `data "archive_file"` over `apps/lambda/<fn>/src`, and the Lambda log groups
  are declared and **imported** so retention is Terraform-proven (AC-10), never CLI-clicked.
- **Reproducibility (`T-B.5`, `T-B.6`).** `.terraform.lock.hcl` for all eight surviving root
  stacks (`dev/{01_peripherals,02_lambda}`, `prd/{00_bootstrap,01_tf_state,03_iam,
  04_peripherals,06_lambda}`, `hml/04_peripherals`); `required_providers` in every module; the
  Databricks bootstrap token out of state; ECR `MUTABLE`/`force_delete` and the VPC-CIDR
  all-protocol ingress removed with their stacks; the manual `.keep` step encoded or dropped.
- **Schedule (`T-B.7`).** The hourly PRD `contracts-ingestion` rule is `DISABLED` **in
  Terraform** — Lambda, role and log group kept; the `job_export_gold → gold_to_dynamodb →
  DynamoDB` chain untouched, documented consumer-unverified at CLOSURE (WS-E).
- **Live cleanup, in dependency order (`T-B.8`..`T-B.12`), then proof (`T-B.13`).** Security
  groups → subnets → IGW → VPC (O-3); the empty ECS cluster, two empty ECR repositories, HML
  log groups and ACTIVE `dm-*` task-definition revisions; the legacy dev `gold-to-dynamodb`
  lambda with its role and log group and the orphan firehose role; then the state-bucket key
  space (orphan 0-resource keys, phantom `hml/peripherals` entries — after K9). UC credential
  roles are imported/declared, never deleted. `T-B.13` then plans `dev` + `prd` to 0/0/0.

**Verification.** `terraform fmt -check -recursive` and `validate` per surviving stack, the
AC-10 fresh-clone plan summary, and the AC-11..AC-16 CLI probes (`describe-security-groups`,
`describe-vpcs`, `list-clusters`, `describe-repositories`, `describe-log-groups`,
`list-functions`, `dynamodb scan --select COUNT`, `s3api list-objects-v2`,
`events describe-rule`, `git ls-files 'services/**/.terraform.lock.hcl' | wc -l`).

## 5. WS-C — Databricks artifacts

**Approach.**

- **Drop what the CLI cannot express (`T-C.1`).** The `alert_*` and `genie_ethereum` bundles
  deploy nothing; they are removed and their reinstatement recorded as a deferred backlog
  candidate in CLOSURE. `job_reconcile_orphans` goes with its deleted notebook.
- **Delete the cross-bundle jobs (`T-C.2`, F-06).** `apps/dabs/job_trigger_all` and
  `apps/dabs/job_full_refresh` are removed outright: the DLT bundles already own per-pipeline
  trigger jobs with native ids, and full refresh is `databricks pipelines start-update
  --full-refresh <id>`, documented in `apps/dabs/README.md`. `${resources.pipelines.*.id}`
  does not cross a bundle boundary and a display-name `lookup` would couple bundles through
  `[dev]`-prefixed names — hence the ADR-004 corollary "no bundle references another bundle's
  resource", recorded in memory by `T-E.4`. The DLT `schedule:` blocks go too — the field is
  silently dropped, so leaving it is a lie.
- **Guard the host everywhere, de-personalise (`T-C.3`).** `dev`, `hml` and `prod` all read
  the host from a `DATABRICKS_HOST`-style env var or bundle variable, prod's with **no
  default**, so `validate -t prod` fails unset and no `cloud.databricks.com` literal survives
  (AC-19 and the guard now agree). Dashboards take the catalog as a parameter; the published
  embed setting matches the bundle; `run_as` is the service principal in every target; bucket
  variables align to SPEC §2.2 B2's pinned names (K5).
- **HML Unity Catalog (`T-C.7`).** The `hml` storage credential and external location are
  created/updated via `databricks storage-credentials` / `external-locations` against
  `dm-databricks-hml-s3-role` and the two canonical buckets — the step that makes AC-18b's
  `head-bucket` + `external-locations get` pair meaningful rather than nominal.
- **Scope the maintenance jobs (`T-C.4`).** `job_ddl_setup` / `job_delta_maintenance`
  restricted to non-DLT objects or removed; f-string SQL replaced; the app-logs silver filter
  retargeted off the retired producers' logger names; `apps/dabs/README.md` rewritten.
- **Converge live to repo (`T-C.5`, `T-C.6`).** Validate every surviving bundle in `dev` and
  `hml` (and prove `prod` fails without the host variable), then deploy both — including the
  never-deployed Fluent-Bit app-logs reader and the pre-R1 hml ethereum pipeline — and remove
  the stale `.bundle/dd-chain-explorer` roots and the orphan dashboard. **No prod deploy** (O-6).

**Verification.** `bundle validate -t dev|-t hml` per bundle (exit 0) and `-t prod` unset-host
(non-zero); `bundle summary`; `workspace export` diffed against each repo notebook (AC-18);
`jobs list`; `s3api head-bucket` + `external-locations get` (AC-18b);
`grep -rniE '@|cloud.databricks.com|"dev\."' apps/dabs/`. ACs: AC-17..AC-19.

## 6. WS-D — Dead code, supply chain, quality gates, tests, docs

**Approach.**

- **Tests before deletions (`T-D.1` → `T-D.2` → `T-D.3`).** The repo-level `tests/` tree is
  written first — both Lambda handlers, the DABs job scripts, the DLT expectation functions
  (local PySpark), plus the CI-script cases the suite lacks, each declaring intent and size at
  birth (`dadaia-test-stewardship`). Only then the `qa-engineer` deletion/demotion verdict,
  and only then the deletions: `apps/docker/onchain-stream-txs/**`, the six dead
  `dm_chain_utils` modules and their re-exports, `scripts/prod_ecs_logs.py`, the unreferenced
  operator scripts, `hml_integration_test_optimized.sh`, and the `img/` slop.
- **Supply chain (`T-D.4`, D15).** `scripts/build_lambda_layer.sh` installs third-party deps
  with `pip install --require-hashes -r apps/lambda/requirements.lock -t build/` and the
  library with `pip install ./utils -t build/ --no-deps` — the **path** requirement closes
  dependency confusion; `--no-index` is wrong here, since the transitive deps do come from the
  index, hash-pinned. The zip lands in `.lambda_zip/` (untracked, gitignored); the public
  `==0.2.9` pin disappears; every requirement is `==`-pinned. Upload, `-var` pass-through and
  `pip-audit -r` are WS-A's, the bucket and Terraform variables WS-B's (K6). `T-D.7` sets the
  library version declarations to `0.5.0` after K3.
- **Quality gates and docs (`T-D.5`, `T-D.6`).** `ruff` (format + check) and `mypy` configured
  and passing; state directories gitignored; the duplicate test tree, residual key-tail
  logging and bulk parameter-listing helper removed. The Makefile becomes thin wrappers over
  the scripts CI runs, so every documented target resolves; `README.md`, `docs/**` (incl. the
  bootstrap runbook), app READMEs, DLT notebook headers, DDL comments and the integration-test
  prerequisites are rewritten to the post-capture scope.

**Verification.** `ruff format --check . --no-cache`, `ruff check . --no-cache`, `mypy`,
`pytest -p no:cacheprovider`, `git status --porcelain` empty, `make -n <target>` per
documented target, the AC-20/AC-21/AC-24 greps. ACs: AC-20..AC-24.

## 7. WS-E — Governance, dispositions, memory truth

**Approach.**

- **Constitution (`T-E.1`).** Re-authored from the archived 231-line version, scoped to the
  infra / CI / Databricks reality — no capture-layer law, no aspirational REST API.
- **Bug ledger (`T-E.2`).** The misfiled tooling bug gets a terminal `rejected` event whose
  `--reason` names its upstream re-registration; the migration-synthesized
  resolved-before-reported timestamp anomaly on `drift-04-kafka-avro-dead-code` is
  corrected so `dadaia specs doctor` (SPEC-DOC-033) is clean.
- **CLOSURE-phase work (`T-E.4`..`T-E.8`).** Three ADR edits — the capture-deprecation ADR,
  the rewritten ADR-005, and C2's ADR-004 corollary — land in `specs/memory/architecture.md`,
  gate-writable in DEFINITION/CLOSURE only, so they are authored **with** the memory update,
  never during implementation. Then: memory atoms (SPEC §8) → `CLOSURE.md` with a disposition
  row per DRIFT-01..31 and per 2026-06-11 finding id → artifact GC sweep → `git mv` of both
  audit directories (each with a `DISPOSITION.md` naming v0.5.0) and of the release directory.

**Verification.** `dadaia specs doctor` (0 errors), `dadaia backlog doctor` (clean),
`dadaia bugs status` (0 open), `wc -l specs/constitution.md`, `ls specs/audits/_archive/`.
ACs: AC-25..AC-28.

## 8. Review cadence and agent assignment

| Boundary | Validators | What it unlocks |
|---|---|---|
| Per task | implementer discipline (TDD, local gates, handoff) | nothing — marker stays `[-]` |
| **alpha-1** (`T-R.1`) | `qa-engineer` only | `[x]` on WS-A..WS-E implementation tasks; a qa artifact committed to the branch. No push, no PR, no CLOSURE |
| **rc-1** (`T-R.2`) | `qa-engineer` + `code-reviewer` (six-axis on the delta) + `security-reviewer` (diff-based) — all APPROVE the **same** commit | memory update → CLOSURE → archive, then ship |
| **ship** (`T-R.3`) | `security-reviewer` push verdict on `origin/develop..develop` | merge `feature/0.5.0` → `develop`, push, PR `develop` → `main`, watch CI to green, tag `v0.5.0` |
| **re-audit** (`T-R.4`) | `project-auditor` | release closes only at score ≥ 7 with no dimension < 5 |

Any `REQUEST_CHANGES`, CRITICAL/HIGH finding or missing evidence returns the work to
implementation (`dd-release-implement` §4).

**Assignment.** `software-engineer` — all repository code, IaC, workflows, bundles, tests,
docs and every live AWS/Databricks/Terraform operation. `qa-engineer` — the deletion/demotion
verdict (`T-D.2`), alpha-1 (`T-R.1`), the qa leg of rc-1. `code-reviewer` — six-axis at rc-1.
`security-reviewer` — the IAM verdict (`T-A.2`), the secret-surface verdict, rc-1, the
pre-push diff verdict. `product-engineer` — WS-E, memory, `CLOSURE.md`, `ACTIVE.md`, archive.
`coordinator` (project-manager + operator) — the `00_bootstrap` apply, `gh` repository
settings and the IAM key deactivation. `project-auditor` — the re-audit (`T-R.4`).

## 9. Rollback per live mutation

| Mutation | Task | Reversible? | Rollback path |
|---|---|---|---|
| Terraform `force-unlock` on two stacks | `T-B.1` | n/a | Confirm no in-flight run first (`gh run list --status in_progress`); a wrongly released lock is re-acquired by the next plan |
| Apply of `prd/00_bootstrap` (the four deploy roles) | `T-A.3` | Yes | Purely additive — a **new** stack and a new state key, touching no existing resource. Rollback is `terraform destroy` of `00_bootstrap` alone (or `git revert` + re-apply); nothing else references it until `T-A.4` publishes the variables, and the static-key path stays usable until then. Because CI never applies this stack, a bad rollback cannot be re-introduced by a workflow run |
| Removal of `oidc.tf` from `prd/03_iam` | `T-B.3a` | Yes | `git revert` and re-apply; run it only after `AC-2`/`AC-2b` prove the `00_bootstrap` roles work, so the stacks are never both without roles. Both stacks are planned before either is applied |
| Create the `dm-chain-explorer-artifacts` bucket | `T-B.14` | Yes | Additive and empty at creation; `terraform destroy` of the resource returns to the status quo. Versioning is ON, so an overwritten layer object is recoverable by version id; layer keys are content-addressed, so a rollback is "point the `-var` at the previous `<sha256>` key" — no rebuild needed |
| Delete GitHub secrets | `T-A.4` | **No** (values unrecoverable) | Forward-only: the OIDC roles replace them. Do not delete until `T-A.3` proves the roles exist and `T-A.4` published the variables |
| Deactivate the CI IAM access key | `T-A.5` | Yes | `aws iam update-access-key --status Active` — deactivation is chosen over deletion precisely to keep this path |
| Default-branch rename `master`→`main` | `T-A.11` | Yes | Rename back via `gh`; GitHub preserves redirects; local clones run `git remote set-head origin -a`. The `develop`→`main` PR is merged with a **merge commit**, so `master`'s 4 unique commits stay reachable and a revert is an ordinary revert, not a history reconstruction |
| Branch protection / environment reviewers | `T-A.10` | Yes | Settings are re-editable; capture the prior `gh api …/protection` JSON before changing |
| Delete 24 security groups, then the legacy VPC / subnets / IGW | `T-B.8` | **No** | Snapshot `describe-security-groups|vpcs|subnets|internet-gateways` to `.dadaia/tmp/software-engineer/<date>/` first and verify zero attached ENIs; recreation is possible from the snapshot but would be a new deliberate change, not a rollback |
| Delete ECS cluster, ECR repos, log groups, task-def revisions, the legacy dev lambda + role and the orphan firehose role | `T-B.9`, `T-B.10` | **No** | Both repositories verified empty by `list-images`; log groups exported only if non-empty; task-def revisions stay listable as INACTIVE; `get-function` config and role policies snapshotted before deletion — the function is superseded, not migrated |
| HML stack destroys | `T-B.4` | Partly | Re-declare from git history and apply; the kept buckets are never in the destroy set — the plan is reviewed under the informed gate before `destroy_ack` |
| Delete orphan state keys / phantom entries | `T-B.11` | Yes if versioned | Confirm bucket versioning is ON and restore the object version; otherwise delete only keys proven 0-resource. **Never** copy state files to local disk — they carry credential material (`DADAIA.md` §8) |
| Disable the ingestion schedule | `T-B.7` | Yes | Flip the Terraform flag back and apply — a one-line, plan-visible change |
| Bundle redeploys (`dev`, `hml`) | `T-C.6` | Yes | `git checkout <prev-ref> -- apps/dabs && databricks bundle deploy -t <target>`; no data is flowing, so no pipeline state is at risk |
| Import of the Unity-Catalog credential role | `T-B.12` | Yes | `terraform state rm` returns to the unmanaged status quo; the role itself is never modified |
| Code / test deletions | `T-D.3` | Yes | `git revert` — history is the archive (D3) |

## 10. Validation plan (run in this order at rc-1)

1. `ruff format --check` · `ruff check` · `mypy` (AC-22); `pytest -p no:cacheprovider` and `pytest scripts/ci/tests utils/tests` — all green (AC-9, AC-23).
2. `terraform fmt -check -recursive` · `validate` per surviving stack · `actionlint` — clean.
3. `databricks bundle validate -t dev|-t hml` per bundle, `-t prod` unset-host expected-fail (AC-17).
4. `deploy_cloud_infra` plan on `dev` + `prd` **from a fresh clone**: `0 to add, 0 to change, 0 to destroy` (AC-10).
5. AWS CLI absence/presence probes AC-11..AC-16; Databricks state probes AC-18/AC-18b; IAM `simulate-principal-policy` negatives (AC-2b).
6. `plan_on_pr` on a PR into `main` from a fresh clone — conclusion `success` (AC-4); the empty-variable preflight dry run (AC-3b).
7. `dadaia specs doctor` · `dadaia backlog doctor` · `dadaia bugs status` (AC-25, AC-28).
8. Ship gate: all of the above **plus** the `project-auditor` re-audit ≥ 7, no dimension < 5.

Risks live in SPEC §9; §9 above is the operational rollback contract they reference.
