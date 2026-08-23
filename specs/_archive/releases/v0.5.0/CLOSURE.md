# Closure: Release — v0.5.0

> **Status:** Aprovado
> **Release ID:** v0.5.0
> **Owner:** product-engineer
> **Closed:** 2026-08-23

## Summary

v0.5.0 is the remediation release that turned a platform documented as if it ran into a
platform that actually works. The audit verdict it answers was *"a correctly-retired
capture layer with no successor yet, documented as if it still ran, and governed by a CI
that cannot authenticate."* All three halves of that sentence are now false.

**CI authenticates.** Four least-privilege GitHub OIDC roles live in a new
operator-applied `prd/00_bootstrap` stack that CI itself may never apply — the bootstrap
paradox is designed away rather than re-lived — capped by a permissions boundary carried
by every project role, with an explicit self-mutation `Deny` proven negatively by
`simulate-principal-policy`. The four role ARNs are published as repository variables by a
checked-in script, every role-assuming job fails fast on an empty variable, and the static
AWS keys are deleted with the legacy IAM key deactivated. The first end-to-end pipeline run
in this repository's history went green on PR #29.

**The declared infrastructure is the live infrastructure.** Eleven capture-era and
never-applied stacks and three modules were deleted; the unmanaged legacy VPC, its 24
leaked security groups, the empty ECS cluster, 42 orphan log groups, 62 stale task-
definition revisions, the orphan Lambda and roles, both April state locks and nine
zero-resource state keys are gone. HML is a minimal two-bucket lane with its own Unity
Catalog credential; the Databricks workspace holds exactly the seven bundles the
repository declares, deployed to `dev` and `hml` with live state equal to the repo. The
capture-era Python and its tests were deleted under a QA verdict after the live-surface
pyramid existed, and the repository gained its first quality gates.

**Governance is real.** `main` is the default branch, protected by a pull request and
nine required checks; `develop` is protected; both deployment environments require the
operator as reviewer. v0.5.0 shipped through that gate — PR #29 merged as merge commit
`9ad2165`, tagged `v0.5.0`.

The platform stays deliberately parked: raw ingestion is empty until `dd-chain-capture`
delivers, DLT triggers are paused and the hourly ingestion schedule is disabled. That
posture is now written law, not an accident — ADR-007 in `specs/memory/architecture.md`
records the supersession, the S3-only boundary, and the criteria that end it.

## Tasks completed

Commit shas below name the pushed integration points, not per-task commits: the release's
code landed on `develop` in two pushed batches (`803238c`, `4d476ac`, both carrying an
APPROVED security push verdict) and shipped to `main` as merge commit `9ad2165` (tag
`v0.5.0`). Per-task evidence notes live in `TASKS.md`.

| Task ID | Description | Final commit |
|---------|-------------|--------------|
| T-A.1 | Author `prd/00_bootstrap` — 4 OIDC roles, permissions boundary, self-mutation `Deny`, trust-`sub` pinning | `ec8bcb9` (rev3), `4d476ac` |
| T-A.2 | Security verdict on the bootstrap IAM delta (rev1 REJECTED → rev2 REJECTED → rev3 APPROVED) | `ec8bcb9` |
| T-A.3 | Apply `prd/00_bootstrap` with operator credentials — 13 IAM resources + rev4/rev5 deltas | live AWS; post-apply plan `No changes` |
| T-A.3b | Negative least-privilege proof — `simulate-principal-policy` on all 4 roles | `4d476ac` |
| T-A.4 | `publish_oidc_vars.sh`, the fail-fast preflight, the 4 variables published, static + capture-era secrets deleted | `4d476ac` |
| T-A.5 | Legacy CI IAM access key set `Inactive` | live AWS |
| T-A.6 | Capture lane purged from the application deploy workflow; HML lane scripts reduced | `803238c` |
| T-A.7 | CI safety batch — concurrency, both-branch PR trigger, suites + `pip-audit` + layer build wired in, pinned tooling, bump workflow deleted | `803238c` |
| T-A.8 | Truthful `stack_map.json`, lock-free read-only plan path, new assertion cases | `803238c` |
| T-A.9 | One version axis = the SDD release id | `803238c` |
| T-A.10 | Branch protection on `main` (9 checks) and `develop`; environment reviewers; stale branches listed only | GitHub settings; `docs/governance/stale-branches-v0.5.0.md` |
| T-A.11 | `master`→`main` rename; cut-over PR #29 opened; required check names captured | PR #29 |
| T-B.1 | Both April state locks released | live AWS; lock scan `0` |
| T-B.2 | Capture-era and never-applied stacks and modules deleted | `803238c` |
| T-B.3 | Module/grant surgery — firehose branch, capture grants, E2 role set, account-uuid default, dead remote-state aliases | `803238c` |
| T-B.3a | `oidc.tf` removed from `prd/03_iam` and applied — 12 capture-era IAM resources destroyed | live AWS; post-apply plan exit 0 |
| T-B.4 | HML reduced to the pinned two-bucket lane + `dm-databricks-hml-s3-role` | live AWS; `head-bucket` 200 ×2 |
| T-B.5 | `.terraform.lock.hcl` for all 8 root stacks; `required_providers` in every module | `803238c` |
| T-B.6 | Services hardening — no token in state, ECR/VPC declarations gone with their stacks, `.keep` pattern retired | `4d476ac` |
| T-B.7 | PRD `contracts-ingestion` schedule DISABLED (scheduler API; Terraform path rides T-B.14) | live AWS |
| T-B.8 | Legacy VPC fully deleted — 26 security groups, 4 subnets, IGW, route table, VPC | live AWS; probe `0` |
| T-B.9 | ECS cluster, 42 HML/container-insights log groups, 62 task-definition revisions removed | live AWS |
| T-B.10 | Orphan legacy Lambda, its role and log group, and the firehose role deleted | live AWS |
| T-B.11 | 9 zero-resource state keys removed; bucket reduced to 7 survivors + `capture/ecr` | live AWS |
| T-B.12 | `dm-databricks-dev-s3-role` imported into `dev/01_peripherals`; UC credential validate PASS | live AWS |
| T-B.13 | Fresh-clone plan proof on every kept stack (PR #29 CI round 4) | PR #29 |
| T-B.14 | Artifact store + layer/log-group rewire authored; live apply deferred (operator ruling) | `4d476ac` |
| T-C.1 | No-op `alert_*`/`genie_ethereum` bundles and `job_reconcile_orphans` dropped | `803238c` |
| T-C.2 | `job_trigger_all` and `job_full_refresh` deleted; DLT `schedule:` blocks removed | `803238c` |
| T-C.3 | Host guarded on every target, catalog parametrised, service-principal `run_as`, hml names aligned | `803238c` |
| T-C.4 | DDL/maintenance jobs scoped or removed, f-string SQL removed, silver filter retargeted, README rewritten | `803238c` |
| T-C.5 | Every surviving bundle validated in `dev` and `hml` | bundle validate exit 0 |
| T-C.6 | `dev` + `hml` deployed so live == repo; 11 orphan jobs and stale `.bundle` roots deleted | live workspace |
| T-C.7 | HML Unity Catalog credential + 2 external locations created and validated | live workspace |
| T-D.1 | Live-surface pyramid written before any deletion | `4d476ac` |
| T-D.2 | `qa-engineer` verdict on the deletion/demotion map | handoff `2026-08-23T162658Z` |
| T-D.3 | Capture-era code, tests and `img/` slop deleted | `4d476ac` |
| T-D.4 | Supply chain closed — path-installed library, hash-pinned lock, layer build script, binaries untracked | `4d476ac` |
| T-D.5 | ruff + mypy configured and passing; worktree cleaned; residual logging removed | `4d476ac` |
| T-D.6 | Makefile reduced to real wrappers; README/docs/notebook headers rewritten | `4d476ac` |
| T-D.7 | Library version declarations set to the release id | `4d476ac` |
| T-E.1 | `specs/constitution.md` authored (154 lines, scoped to infra/CI/Databricks) | `4d476ac` |
| T-E.2 | Bug-ledger repair — terminal event for the misfiled tooling bug | `4d476ac` |
| T-E.3 | SDD-tree verification — no release SPEC outside `_archive/`, v0.4.0 archive and backlog intact | `4d476ac` |
| T-E.4 | Capture-deprecation ADR-007, ADR-005 rewritten streaming-only, ADR-004 corollary | this closure |
| T-E.5 | Memory atoms updated to post-release truth | this closure |
| T-E.6 | This CLOSURE.md | this closure |
| T-E.7 | `## Intake candidates` compiled | this closure |
| T-R.1 | alpha-1 — `qa-engineer` APPROVED | handoff `2026-08-23T175530Z` |
| T-R.2 | rc — qa + code-review + security all APPROVED on the same commit | `03b6dec`, `f2f268f`, `f29a1b0` |
| T-R.3 | Ship + `main` cut-over — PR #29 merged, `develop` reconciled, tag `v0.5.0` | `9ad2165` |
| T-R.4 | Re-audit — 6.1 live / 7.4 projected (baseline 3.6); ship gate not yet met on live state | `specs/audits/20260823T182948Z-4db47555/` |

## Validations

| Description | Command | Evidence |
|-------------|---------|----------|
| Full CI pipeline green end to end for the first time | PR #29 checks | 9/9 checks green; merge commit `9ad2165` |
| OIDC roles exist, scoped, boundary-capped | `aws iam list-roles` / `get-role-policy` / `terraform show -json` | T-A.3 apply summary; 78 static assertions green |
| Least privilege proven negatively | `aws iam simulate-principal-policy` | `iam:UpdateAssumeRolePolicy`(self) and `iam:CreateAccessKey` → `explicitDeny` on all 4 roles; `s3:GetObject`(state) → `allowed` |
| Role variables published, static/capture secrets deleted | `gh variable list`, `gh secret list` | 4 `AWS_DEPLOY_ROLE_*` present; secret store holds Databricks names only |
| Legacy IAM key deactivated | `aws iam list-access-keys` | 2025-vintage key `Inactive` |
| Fresh-clone plan clean on every kept stack | `deploy_cloud_infra` plan phase (PR #29 CI round 4) | dev/01, dev/02, hml/04, prd/03, prd/04, prd/06 planned green from the runner's clone; prd/06 layer step skip-with-warning (store deferred) |
| State locks released | `aws dynamodb scan --select COUNT` | rows with `Info` → 0 |
| Live orphans removed | `describe-security-groups`/`describe-vpcs`/`list-clusters`/`describe-log-groups`/`list-functions` | 0 SGs, 0 project VPCs, no project ECS cluster, 0 HML log groups, no legacy function |
| State bucket reduced | `aws s3api list-objects-v2` | 7 project keys + `capture/ecr` |
| Ingestion schedule disabled | scheduler `get-schedule` | `State: DISABLED` |
| HML UC lane live | `head-bucket` ×2, `external-locations get`, `storage-credentials get` | 200/200; both locations validate PASS on `dm-databricks-hml-s3-role` |
| Bundles validate and deployed == repo | `databricks bundle validate -t dev|-t hml`, `bundle summary`, notebook export diff | exit 0 per bundle; `[dev] dm-app-logs` export == repo; 7 bundles, 6 in-bundle jobs, no orphans |
| Test suite green | `pytest -p no:cacheprovider` | 143/143 |
| Quality gates clean | `ruff format --check`, `ruff check`, `mypy`, `git status --porcelain` | all exit 0, tree clean |
| Workflow security posture | `zizmor`, `actionlint`, `shellcheck` | zizmor 0 high (was 9 error); actionlint clean; 18 shellcheck findings fixed |
| Branch and environment governance | `gh repo view`, `gh api …/branches/{main,develop}/protection`, `…/environments` | default `main`; 9 required checks + PR on `main`; `develop` protected; operator reviewer on `hml`/`production` |
| Drift detection reachable | `gh api …/contents/.github/workflows/drift_detection.yml?ref=main`, `gh workflow view` | 200, enabled; first cron **pending** (recorded, not claimed as evidence) |
| Reviews | qa / code / security handoffs | qa rc-2 APPROVED, code rc-2 APPROVE, security APPROVED (`03b6dec`, `f2f268f`, `f29a1b0`) |
| Re-audit against the ship gate | `project-auditor` | 6.1 live / 7.4 projected — gate (≥7, no dimension <5) **not yet met on live state** |

## Size accounting

Measured by the coordinator (2026-08-23, this session), production surface only:

```
git diff --numstat 9ad2165^1 9ad2165 -- ':!specs' ':!tests' ':!docs'
→ 301 files, +14,029 / −17,737 lines — net −3,708
```

The release **shrank** the production tree by ~3.7k lines while adding the whole
OIDC bootstrap stack, CI hardening and runbooks — the dead-code purge (WS-D) and
capture-era IAM removal outweighed every addition.

| Metric | Value |
|--------|-------|
| Production LOC added | pending measurement |
| Production LOC deleted | pending measurement (net strongly negative — 11 Terraform stacks, 3 modules, the whole `apps/docker` tree, 6 library modules and the capture-era test suites were deleted) |
| Production LOC net | pending measurement |

| Ceiling | Before | After | Justification |
|---------|--------|-------|----------------|
| `C90` (`max-complexity`) | none — no lint configuration existed | pinned by the new ruff configuration | n/a — first pin, not a decrease |
| `PLR1702` (`max-nested-blocks`) | none | pinned by the new ruff configuration | n/a — first pin, not a decrease |

**Nesting-violation count:** 0 — `ruff check` exits 0 against the pinned ceilings.

## Drifts

### bootstrap-iam-three-revisions

**Description:** The bootstrap IAM policy set was rejected twice by security review before
approval, then needed two further deltas after the live apply (rev4 — the boundary blocked
the Unity Catalog role's self-assume; rev5 — the readonly/deploy read gap on non-`Bucket`-
infix S3 `Get*` actions, `DescribeLogGroups` on `log-group:*`, and exact ARNs for the PRD
legacy eponymous table and log group).

**Resolution:** Each rejection was fixed at the cause rather than by widening scope: the
permissions boundary stayed, and the fixes narrowed `Deny`s or added precisely-scoped
`Allow`s. The boundary was retrofitted onto all 8 pre-existing project roles in one commit
so the CreateRole→PutRolePolicy→PassRole chain has no uncapped target left.

**Memory updates:** `specs/memory/product/aws-resources.md` (IAM table now states the
boundary as carried by every project role), `specs/memory/product/cicd-pipeline.md`.

### prd-artifact-store-deferred

**Description:** `T-B.14`'s artifacts bucket and the `prd/06_lambda` layer rewire could not
be applied: the operator authorization for the live cutover excluded creating new
productive PRD resources.

**Resolution:** Operator-ratified deferral. The code landed and validates; the CI layer
steps skip with a warning while the store is absent, so nothing fails silently.
`T-B.7`'s Terraform-path schedule disable rides on the same apply — the schedule itself is
already DISABLED live via the scheduler API, so the declared and live states agree.

**Memory updates:** `specs/memory/product/aws-resources.md` (artifacts bucket marked
declared-not-applied; Lambda log-group retention marked declared with import pending),
`specs/memory/architecture.md` (limits).

### prd-03-iam-now-empty

**Description:** After the capture-era IAM removal and the OIDC relocation, `prd/03_iam`
declares no resource at all — its apply destroyed 12 live resources and left an empty state
key.

**Resolution:** The stack directory and state key were kept, holding only the bootstrap
remote-state plumbing so a future PRD role need not reintroduce it. Retiring the stack
entirely is listed as an intake candidate rather than done unreviewed.

**Memory updates:** `specs/memory/product/aws-resources.md` (stack table row marks it
empty).

### session-gated-live-steps

**Description:** Several live-destructive steps (bulk deletions, `terraform apply`) were
blocked by the session action policy mid-release, leaving tasks PARTIAL.

**Resolution:** The blocked steps were compiled into `docs/runbooks/v0.5.0-live-cutover.md`
and executed under explicit operator authorization, then re-probed. Every affected task
carries both the PARTIAL note and the operator-authorized completion note in `TASKS.md`.

**Memory updates:** none — the outcome, not the route, is what memory records.

### ci-yaml-invalidity-missed-by-two-reviews

**Description:** A 42-file workflow refactor shipped invalid YAML that two reviews did not
catch; it surfaced only when CI ran.

**Resolution:** Fixed at the cause and, more importantly, `actionlint` (pinned installer +
checksum) and `zizmor` now run on the workflow set in the PR gate, so workflow validity is
machine-checked rather than review-checked.

**Memory updates:** `specs/memory/product/cicd-pipeline.md`,
`specs/memory/quality-assurance.md`.

## Memory updates

- `specs/memory/architecture.md` — layer map, contracts, environment topology and deploy
  order rewritten to the 8 surviving stacks and OIDC-live CI; **ADR-007** (capture
  deprecation, S3-only boundary, parked-until-delivery, sunset criteria) added; **ADR-005**
  rewritten to the streaming-only reality; **ADR-004** gained the "no bundle references
  another bundle's resource" corollary.
- `specs/memory/product/cicd-pipeline.md` — rewritten: the "Estado real e lacunas" gap
  list is gone, replaced by the working OIDC model, the quality gate, the runner-hardening
  posture and the branch/environment governance; workflow inventory drops the deleted bump
  workflow and adds Scorecard.
- `specs/memory/product/aws-resources.md` — rewritten to the post-cutover inventory:
  stack↔state-key table, the four OIDC roles and the CI boundary, the hml lane, the
  artifacts bucket as declared-not-applied, 7 state keys + `capture/ecr`, and a closing
  "Retirado do inventário" list of everything that no longer exists.
- `specs/memory/product/medallion-pipelines.md` — trigger model without DLT `schedule:`,
  in-bundle trigger jobs, deployed-equals-repo statement; the broken-companion-job gap list
  removed.
- `specs/memory/product/serving-layer.md` — dashboards parametrised and service-principal
  `run_as`; alerts/Genie removed from the surface; the gold-export chain kept and
  documented as consumer-unverified.
- `specs/memory/product/capture-layer.md` — parked-until-delivery posture pointing at
  ADR-007, the field-name compatibility TODO kept as an open verification, and the residue
  paragraph replaced by "No residue".
- `specs/memory/quality-assurance.md` — the real pyramid (143 tests, four suites, all in
  CI), the gates now enforced on every PR, and the test-stewardship declarations.
- `specs/memory/tech-stack.md` — path-installed library and hash-pinned requirements, the
  three surviving library modules, four Terraform modules with pinned providers and
  committed lock files, the CI toolchain under OIDC, and **one** version axis.
- `specs/memory/product/data-catalog.md` — **no change**: the release deployed no schema
  and created no object; the Unity Catalog inventory is unchanged.
- `specs/memory/product/index.md` + `catalog.json` — **no change to ranks or atom set**:
  no feature was added, removed or reordered by this release.

## Dispositions

No bug was picked into this release (the ledger's only live record was a misfiled tooling
bug, terminally dispositioned by `T-E.2` and re-registered upstream). The backlog slugs the
SPEC declared in `**Consumes:**` were purged from `## ACTIVE` at definition time; each is
recorded terminal here.

### Backlog consumed

| Record | Kind | Terminal disposition | Evidence |
|--------|------|-----------------------|----------|
| `v050-ci-oidc-auth-recovery` | backlog | `SHIPPED` | T-A.1..T-A.5 rows above |
| `v050-deploy-workflow-capture-lane-purge` | backlog | `SHIPPED` | T-A.6 |
| `v050-ci-safety-guards-concurrency-lockfile` | backlog | `SHIPPED` | T-A.7, T-A.8, T-B.5 |
| `v050-repo-governance-branch-protection-default-branch` | backlog | `SHIPPED` | T-A.10, T-A.11, T-R.3 |
| `v050-version-axis-unification` | backlog | `SHIPPED` | T-A.9, T-D.7 |
| `v050-public-repo-secret-store-and-pii-hygiene` | backlog | `SHIPPED` | T-A.4, T-A.5, T-C.3 |
| `v050-dependency-confusion-and-lambda-layer-rebuild` | backlog | `SHIPPED` | T-D.4 (+ T-B.14 apply deferred) |
| `v050-dead-code-and-docs-purge-capture-era` | backlog | `SHIPPED` | T-D.3, T-D.6 |
| `v050-dead-iac-purge` | backlog | `SHIPPED` | T-B.2, T-B.3, T-B.3a |
| `v050-live-infra-cleanup-hml-orphans-state-locks` | backlog | `SHIPPED` | T-B.1, T-B.4, T-B.8..T-B.12 |
| `v050-contracts-ingestion-schedule-and-lambda-path-decision` | backlog | `SHIPPED` | T-B.7 |
| `v050-databricks-deploy-drift-redeploy-live-bundles` | backlog | `SHIPPED` | T-C.5, T-C.6 |
| `v050-databricks-bundle-config-hardening` | backlog | `SHIPPED` | T-C.1..T-C.4, T-C.7 |
| `v050-security-hardening-batch` | backlog | `SHIPPED` | T-A.7, T-B.6, T-C.4, T-D.5 |
| `v050-live-surface-test-pyramid` | backlog | `SHIPPED` | T-D.1..T-D.3 |
| `v050-quality-gates-ruff-mypy-worktree` | backlog | `SHIPPED` | T-D.5 |
| `v050-memory-truth-and-capture-deprecation-adr` | backlog | `SHIPPED` | T-E.4, T-E.5 |
| `v050-audit-dispositions-constitution-bug-ledger` | backlog | `SHIPPED` | T-E.1..T-E.3, this section |

### Bug ledger

| Record | Kind | Terminal disposition | Evidence |
|--------|------|-----------------------|----------|
| `specs/bugs/bugs.jsonl` (`sdd-artifact-linter-mutates-task-markers`) | bug | `Closed` — terminal event appended; not a bug of this context, re-registered upstream in the workspace-library context | T-E.2 |
| `specs/bugs/bugs.jsonl` (`drift-04-kafka-avro-dead-code`) | bug | `Closed` — timestamp anomaly recorded as record-only (the ledger is append-only; no event kind corrects a past event) | T-E.2 |

### Audit `20260823T145726Z-4db47555` — DRIFT-01..31 (31/31)

| Finding | Terminal disposition | Evidence |
|---|---|---|
| DRIFT-01 CI cannot authenticate | `fixed` | T-A.1, T-A.3, T-A.4; PR #29 9/9 green |
| DRIFT-02 deploy workflow re-provisions capture | `fixed` | T-A.6; capture grep → 0 |
| DRIFT-03 v0.4.0 done-but-open | `fixed` | v0.4.0 archived with CLOSURE; re-verified by T-E.3 |
| DRIFT-04 six stale memory atoms | `fixed` | `## Memory updates` above |
| DRIFT-05 audits undispositioned | `fixed` | this section; archived by T-E.8 |
| DRIFT-06 dependency confusion | `fixed` | T-D.4 — path install of `./utils` |
| DRIFT-07 committed layer zip, 31 CVEs | `fixed` (code) — the artifact-store **apply** is a pre-approved deferral | T-D.4, T-A.7, T-B.14 |
| DRIFT-08 admin-escalating deploy roles | `fixed` | T-A.1, T-A.3b — `explicitDeny` on self-mutation, all 4 roles |
| DRIFT-09 public-repo secrets + personal identifier | `fixed` | T-A.4, T-A.5, T-C.3 |
| DRIFT-10 no branch protection, default branch | `fixed` | T-A.10, T-A.11, T-R.3 |
| DRIFT-11 two version axes | `fixed` | T-A.9, T-D.7 |
| DRIFT-12 16 dead Python modules | `fixed` | T-D.3 |
| DRIFT-13 dead IaC | `fixed` | T-B.2, T-B.3, T-B.13 |
| DRIFT-14 CI safety tests never run, stack map lies | `fixed` | T-A.7, T-A.8 |
| DRIFT-15 no concurrency, no lock files, destroy gaps | `fixed` | T-A.7, T-A.8, T-B.5 |
| DRIFT-16 two stale state locks | `fixed` | T-B.1 — lock scan 0 |
| DRIFT-17 24 leaked SGs in the unmanaged VPC | `fixed` | T-B.8 |
| DRIFT-18 Databricks deploy drift | `fixed` | T-C.5, T-C.6 |
| DRIFT-19 broken/no-op DABs assets | `fixed`; alert/Genie reinstatement `deferred` | T-C.1, T-C.2; intake candidate below |
| DRIFT-20 inverted test pyramid | `fixed` | T-D.1..T-D.3 — 143 green, all suites in CI |
| DRIFT-21 hourly ingestion schedule burning quota | `fixed` | T-B.7 — schedule DISABLED |
| DRIFT-22 HML half-alive | `fixed` | T-B.4, T-B.12, T-C.7 |
| DRIFT-23 cross-project capture state + KMS | `deferred` (`capture-ecr-state-and-kms-ownership-transfer`); documentation half `fixed` | T-E.5 (`aws-resources.md`, `capture-layer.md`) |
| DRIFT-24 live orphans | `fixed` | T-B.9, T-B.10, T-B.11 |
| DRIFT-25 prod target, dashboards, DDL/maintenance jobs | `fixed` | T-C.3, T-C.4 |
| DRIFT-26 security hardening batch | `fixed` | T-A.7, T-B.6, T-C.4, T-D.5 |
| DRIFT-27 possibly-dead gold→DynamoDB chain | `fixed` — chain kept and documented consumer-unverified | T-E.5 (`serving-layer.md`), T-C.4 |
| DRIFT-28 docs cite nonexistent targets / dead architecture | `fixed` | T-D.6 |
| DRIFT-29 no quality gates, polluted worktree | `fixed` | T-D.5 |
| DRIFT-30 backlog structure | `fixed` | single-source `BACKLOG.md`; re-verified by T-E.3 |
| DRIFT-31 stub constitution, misfiled bug, timestamp anomaly | `fixed` | T-E.1, T-E.2 |

### Audit `20260611T001412Z-cb56f84c` — 82 lane ids (82/82)

Dispositioned by group exactly as SPEC §7.2 maps them; every id is named.

| Finding id(s) | Terminal disposition | Evidence |
|---|---|---|
| ARCH-C1 | `fixed` | T-B.2 — the monolith and both successor stacks deleted |
| ARCH-C2 | `superseded` by DRIFT-22 → `fixed` | T-B.4, T-C.6 |
| ARCH-H1, CI-H5, CI-H6, CI-H7, CI-M4, CI-M5, CI-M8, CI-L7 | `deferred` (`terraform-single-stack-tree-per-env-tfvars`) — restructuring, not drift | SPEC §3; intake candidate below |
| ARCH-H2, CI-L1, CI-L2, CI-L3, CI-L4, CI-L5 | `fixed` | T-D.6 |
| ARCH-H3, ARCH-M1, ARCH-M2, ARCH-M4 | `fixed` | v0.4.0 memory rewrite; re-asserted by T-E.5 |
| ARCH-H4, ARCH-M9, ARCH-M10, SEC-M-01, SEC-M-02, SEC-L-01, SEC-L-03, SEC-L-04 | `rejected` — obsolete: the streaming peripherals, task definitions and capacity model were destroyed and their modules deleted | T-B.2, T-B.3 |
| ARCH-H5 | `fixed` | T-E.4 — ADR-007 |
| ARCH-H6, CI-H2, CI-M7 | `fixed` | T-B.5, T-A.7, T-D.5 |
| ARCH-M3, ARCH-M5 | `fixed`; Genie reinstatement `deferred` | T-C.1, T-C.3 |
| ARCH-M6 | `fixed` | T-D.3 (code), T-B.3 (grants) |
| ARCH-M7, CI-L6 | `fixed` | T-D.5 — worktree clean |
| ARCH-M8 | `deferred` (`rest-api-public-endpoint`); the stray legacy spec is archived | T-E.3 |
| ARCH-L1, ARCH-L2, ARCH-L4 | `fixed` | T-D.3, T-D.6 |
| ARCH-L3, ARCH-L7, SEC-L-02 | `fixed` | T-B.2, T-B.6, T-B.9 — `.keep` pattern retired with `folder_prefixes` |
| ARCH-L5 | `rejected` — advisory only; the divergent surfaces were deleted and survivors keep one prefix | T-B.2, T-D.3 |
| ARCH-L6 | `rejected` — obsolete: the dev compose stack no longer exists | T-D.3 |
| ARCH-L8 | `fixed` — already relocated at intake, re-verified with no survivor found | T-E.3 |
| CI-C1, CI-C2, CI-C3, CI-H1, CI-H3, CI-H4, CI-H8, CI-M2, CI-M3 | `fixed` in v0.3.0 | `_archive/releases/v0.3.0/CLOSURE.md`; concurrency residual → DRIFT-15 |
| CI-M1 | `fixed` — v0.3.0 partial + the HML teardown residual | T-A.6 |
| CI-M6 | `fixed` | T-D.4, T-D.7 |
| CI-M9 | `fixed` — bump workflow deleted, drift workflow gets a group | T-A.7 |
| CI-M10 | `fixed` | T-A.9, T-A.10, T-R.3 |
| CI-M11 | `fixed` | T-B.3 (Terraform), T-D.6 (Makefile) |
| SEC-H-01 | `rejected` — debunked: the logged value is an SSM parameter **name**, not a secret; the residual name-logging is hardened | T-D.5 |
| SEC-H-02, SEC-I-01, SEC-M-05 | `fixed` — v0.3.0 code half + the live half here | T-A.1..T-A.5 |
| SEC-M-03 | `fixed` | T-B.6 — no token persisted in state |
| SEC-M-04 | `deferred` (`encryption-at-rest-posture-decision`) — no new data at rest | SPEC §3; intake candidate below |
| SEC-L-05 | `fixed` | T-D.5 — scanner-ignore blind spot closed |
| SEC-I-02, SEC-I-03 | `record-only` — positive observations, no fix surface; both properties preserved and the required environment reviewers added | T-A.10 |
| DRIFT-N01, DRIFT-N02, DRIFT-N03 | `fixed` | T-B.7 (schedule disabled, Lambda kept), T-E.4 (ADR-005 rewritten) |
| DRIFT-N04, DRIFT-N05, DRIFT-N11, DRIFT-N12 | `fixed` | v0.4.0 memory rewrite — the drifting frontmatter field no longer exists |
| DRIFT-N06 | `fixed` | v0.4.0 authored the atom; refreshed by T-E.5 after the pyramid landed |
| DRIFT-N07, DRIFT-N09 | `fixed` | T-D.4 — `==` pins on a hash-checked lock |
| DRIFT-N08 | `rejected` — obsolete: those tests were deleted with the capture code and replaced by the live-surface pyramid | T-D.2, T-D.3 |
| DRIFT-N10 | `fixed` | T-D.6 |

Both audit directories are archived to `specs/audits/_archive/` with a `DISPOSITION.md`
naming v0.5.0 — executed by `T-E.8`, after this ledger and after the re-audit gate.

## Test dispositions

`T-D.2`'s `qa-engineer` verdict (APPROVED-CONDITIONAL `2026-08-23T162658Z`, condition
ruled satisfied by substance at rc-2, `2026-08-23T175530Z`) is the authority for every row.
No test was deleted before the replacement existed (O-7).

| Kind | Deleted/expired test | Replacement / disposition | Evidence |
|------|----------------------|----------------------------|----------|
| deletion (capability retired) | `apps/docker/onchain-stream-txs/tests/unit/**` (78 tests) | none — the streaming producer code they covered was deleted; capability moved to `dd-chain-capture` | T-D.2 verdict, T-D.3 |
| deletion (subject removed) | `utils/tests/unit/**` cases covering `dm_kinesis`, `dm_sqs`, `dm_firehose`, `dm_web3_client`, `dm_cloudwatch_logger`, `api_keys_manager` | none — those modules were deleted | T-D.2 verdict, T-D.3 |
| relocation | `utils/tests/unit/**` cases covering `dm_dynamodb`, `dm_etherscan`, `dm_parameter_store` | `tests/utils/test_dm_dynamodb.py`, `test_dm_etherscan.py`, `test_dm_parameter_store.py` | T-D.1 |
| new coverage | — (previously zero) | `tests/lambda/` (both handlers), `tests/dabs/` (job scripts + DLT expectation contracts) | T-D.1 |
| deletion (tombstone) | `scripts/hml_integration_test_optimized.sh` (unconditional `exit 0`) | deleted, not stubbed — a script that always succeeds makes a gate look green | T-D.3 |
| SCAFFOLD retrofit | every surviving test | intent + size declared at rewrite | T-D.1, qa rc-2 |

No test is quarantined, skipped or xfailed; the suite is 143/143 green.

## Record-only observations

| Source (reviewer/handoff) | Observation | Why record-only |
|---|---|---|
| `code-reviewer` `2026-08-23T182018Z` | R-1 LOW — Databricks credentials still injected into 3 HML jobs | awareness-only; the injection is the CLI's supported path today, flagged for the next touch of those jobs |
| `security-reviewer` (`SEC-I-02`, `SEC-I-03` lineage) | destroy guardrails and SHA pinning are positive properties | positive observations, no fix surface; both preserved |
| `project-auditor` re-audit `20260823T182948Z` | live score 6.1 vs projected 7.4 — the delta is entirely the deferred live steps | awareness-only; the gate itself is tracked by `T-R.4`, not by intake |
| `product-engineer` (`T-E.2`) | `drift-04` resolved-before-reported timestamp anomaly | the ledger is append-only and no event kind corrects a past event; correcting it would require inventing one |
| `product-engineer` (this closure) | `data-catalog.md` unchanged — no object was created or dropped | no drift to fix |

## Intake candidates

The closer authors **no** backlog entry. Each residual below is listed for the PM to
compile into the next operator-facing intake report.

### Pre-approved intake (operator-ratified during this release)

- **`terraform-single-stack-tree-per-env-tfvars`** — collapse dev/hml/prd into one stack
  tree with per-environment tfvars; module interface hygiene; hardcoded backend/region
  collapse. Carries ARCH-H1, CI-H5, CI-H6, CI-H7, CI-M4, CI-M5, CI-M8, CI-L7.
- **`capture-ecr-state-and-kms-ownership-transfer`** — move the `capture/ecr` state key and
  the `alias/dd-chain-capture-ssm` KMS key to `dd-chain-capture`'s own state; it is the
  last cross-project resource in this boundary and the third sunset criterion of ADR-007
  (DRIFT-23).
- **`rest-api-public-endpoint`** — specced, zero implementation; own planning session
  (ARCH-M8).
- **`encryption-at-rest-posture-decision`** — CMK vs SSE-S3 posture and S3 raw lifecycle
  tiering, deferred while no new data is at rest (SEC-M-04).
- **Alert / Genie reinstatement** — the deployed Databricks CLI has no resource type for
  either; reinstate when it does (DRIFT-19, ARCH-M5).
- **`T-B.14` residual apply** — create `dm-chain-explorer-artifacts` and apply the
  `prd/06_lambda` / `dev/02_lambda` layer rewire plus the log-group imports, which also
  lands `T-B.7`'s Terraform-path schedule disable. Deferred only because it creates a new
  productive PRD resource.
- **3-repo segregation (the v0.6.0 demand)** — split into `dd-chain-infrastructure` (all
  Terraform + infra CI, fresh repo), a new hyphenated `dd-chain-explorer` (specs, DABs,
  lambdas; fresh git, specs tree carried as content) and `dd-chain-capture` unchanged;
  delete the legacy underscore repository after migration. Operator-approved by grill on
  2026-08-23. Ships with the law that **infrastructure resources are created only via the
  CI pipeline applying Terraform, never by CLI** — to be codified in the repo `AGENTS.md`.

### To be adjudicated

- **Boundary `sts:` regression guard** — add a test pinning the permissions boundary's
  `sts:` allowances so a future edit cannot silently widen them (security LOW).
- **`zizmor --offline` in the gate** — offline mode disables impostor-commit detection;
  decide whether the gate should run online or accept the reduced check (security LOW).
- **Runner hardening is audit-only** — decide whether to move `harden-runner` from audit to
  block mode (security LOW).
- **Raw interpolation in `deploy_cloud_infra.yml`** — one job with a writable token still
  interpolates a value directly; convert to an environment binding (security LOW).
- **`preflight-oidc` logs the role ARN unmasked** — pre-existing; mask or accept
  explicitly (security LOW).
- **`DescribeLogGroups` path-prefix probe** — narrow the `log-group:*` grant if AWS gains a
  prefix-scoped form (security LOW).
- **Pin `log_groups_describe_arn` to its single statement** — add the test that keeps that
  local from being reused elsewhere (security LOW).
- **Retire the empty `prd/03_iam` stack** — directory and state key, once it is agreed no
  PRD-scoped role returns.
- **Repo-scoped Databricks secrets now unreferenced** — the operator may delete or rotate
  them.
- **Rotate-or-accept the public Databricks account UUID** — it is the account's UC external
  id and already public; record the decision either way.
Size accounting (production surface, `git diff --numstat 9ad2165^1 9ad2165 -- ':!specs' ':!tests' ':!docs'`): **301 files, +14,029 / −17,737 lines — net −3,708**. The release shrank the production tree.
  numbers.
- **Drift-detection first cron** — verify the first scheduled run actually fires and reports.

## Artifact GC sweep

Deferred to `T-E.8`, immediately before the archive move: this CLOSURE's evidence pointers
reference handoffs under `.dadaia/handoff/dd-chain-explorer/` (qa `175530Z`, code
`182018Z`, security `164159Z`/`165154Z`/`170327Z`/`195212Z`, the push verdicts) and live
snapshots under `.dadaia/tmp/software-engineer/20260823/live/`, all of which must be
**kept** while the re-audit gate is open — the re-auditor reads them.

| Artifact class | Kept (still referenced) | Deleted/archived | Evidence |
|----------------|--------------------------|-------------------|----------|
| `.dadaia/handoff/dd-chain-explorer/*.handoff.json` (this release) | all — referenced by `## Validations` / `## Test dispositions` | 0 (sweep deferred to T-E.8) | this section |
| `.dadaia/reports/dd-chain-explorer/**` (this release) | audit + intake reports referenced above | 0 (sweep deferred to T-E.8) | this section |
| `.dadaia/tmp/software-engineer/20260823/**` | pre-delete live snapshots referenced by T-B.8..T-B.11 | 0 (sweep deferred to T-E.8) | this section |
| lifecycle run records (this release) | n/a — none produced | 0 | this section |

## Archive decision

**MOVE — blocked pending the ship gate.** `T-E.8` moves both audit directories to
`specs/audits/_archive/` with a `DISPOSITION.md` naming v0.5.0, then
`git mv specs/releases/v0.5.0 specs/_archive/releases/v0.5.0` and repoints `ACTIVE.md`.

The move waits on `T-R.4`: the re-audit scores **6.1 live / 7.4 projected** against a ship
gate of **≥ 7 with no dimension below 5**. The gap is the deferred live steps of
`docs/runbooks/v0.5.0-live-cutover.md`. The release is shipped and tagged; the archive is
held open so the re-audit's outcome lands inside it rather than after it.
