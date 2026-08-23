# PLAN — Release v0.6.0 — Three-repo segregation migration

> **Status:** Aprovado
> **Release ID:** v0.6.0
> **Owner:** product-engineer
> **Depends on:** SPEC.md v0.6.0 (`Aprovado`)
> **Branch:** `feature/0.6.0` in each repository, cut per `DADAIA.md` §4 (Gitflow) — `dd-gitflow-default`

This release moves code between repositories. It adds no capability, so **every
acceptance shape is an equality proof**: the same stack plans clean from a new clone, the
same Databricks object answers to the same id, the same test suite is green, the same
`specs/` tree is byte-identical. Anything that is not an equality is a defect of the
migration, not a feature of it.

## 1. Strategy

1. **Prove before you abandon.** No tree is treated as migrated until its destination
   proves the equality: Terraform by fresh-clone 0-diff (AC-3), Databricks by
   post-import `No changes` (AC-7), tests by a green suite in the new CI (AC-12),
   specs by `diff -r` (AC-15). The legacy repository is abandoned, never edited.
2. **One flip, not a window.** Deploy authority moves exactly once, when the operator
   applies the repointed bootstrap (O-2). Before it, only the legacy repo can deploy;
   after it, only `dd-chain-infrastructure` can. There is no interval in which two
   repositories both hold credentials — the platform is parked, so the gap is free.
3. **Import, never recreate** (ADR-5). The Databricks UC stack is the highest-risk task
   of the release and is written fail-closed: a non-importable object escalates.
4. **The manifest is the contract** (SPEC §6). Every file in the legacy tree ends in one
   of three states with evidence. "We probably don't need it" is not a state.
5. **Deletion is the operator's, last** (ADR-7, O-9). Nothing an agent does in this
   release is irreversible except the bootstrap trust flip, which is a one-line revert.

**Layers affected:** repository topology (three GitHub repositories), Terraform IaC and
its state, both CI control planes, the Lambda artifact seam, Databricks workspace-infra
ownership, the SDD tree's home, and the scoped `AGENTS.md` law of both new repos.

## 2. Cross-workstream couplings (the only ones)

| # | Coupling | Resolution |
|---|---|---|
| K1 | O-2 — neither new repo can assume a role until the bootstrap is repointed and applied | `T-I.6` authors the `github_repo` variable + `artifacts-publish` role → `T-I.7` security verdict → `T-I.8` **operator** apply → `T-I.9` publishes the four variables. Every CI-evidence task depends on `T-I.9` |
| K2 | O-3 — the Lambda stacks cannot plan until artifacts exist | `T-I.10` creates and applies `<artifacts-bucket>` → `T-X.5` publishes the layer + handler objects → `T-V.2` treats the Lambda-stack plan as evidence. Before an object exists the resolve step **skips with a warning** (v0.5.0 behaviour, preserved) |
| K3 | The `resolve_layer` contract has one producer and one consumer in two repositories | The key shape, prefix and `<sha256>` output name are pinned by `T-L.3`'s contract doc **before** `T-I.4` (consumer) and `T-X.5` (producer) are written. One document, two implementations, no second source |
| K4 | O-4 — the UC import must not run against a half-declared stack | `T-I.11` authors the stack and inventories every existing object first; `T-I.12` imports and proves `No changes`. A failure in `T-I.12` stops WS-I and escalates — it never falls forward into a create |
| K5 | O-6/O-7 — the specs handover is a critical section | `T-V.4` is the **only** task that may write `specs/**` while it runs. Every WS-L specs write (`T-L.4`) lands **before** it, in the legacy repo; every post-C-DAY specs write (`T-V.6`..`T-V.9`) lands **after** it, in the new explorer repo |
| K6 | The test suites split across the two repos | `scripts/ci/tests` travels with WS-I (`T-I.13`); `tests/**` travels with WS-X (`T-X.4`). A test lost in either move needs a `qa-engineer` verdict (O-8) — `T-V.1` asserts the union is the v0.5.0 set |
| K7 | Both repos need the same governance settings, and only the operator can set them | `T-I.2` and `T-X.2` are OPERATOR-ONLY and are dependencies of `T-V.1`'s green-CI evidence, not of the content tasks — agents keep authoring while the operator provisions |
| K8 | O-9 — WS-D runs only after the ship gate | `T-D.1`..`T-D.3` depend on `T-V.9` (ship) and on the operator's own validation. No agent-executable task depends on any WS-D task |

Everything else is parallel: WS-I writes only inside `dd-chain-infrastructure`, WS-X only
inside the new `dd-chain-explorer`, WS-L writes governance documents in both plus the
legacy `specs/constitution.md`, WS-V writes evidence, WS-D writes only settings.

## 3. WS-I — `dd-chain-infrastructure`

**Approach.**

- **Skeleton (`T-I.1`).** `git init` in the empty target repo — no remote of the legacy
  repo is ever added, which is what makes ADR-2 structural rather than a promise. Branches
  `main` → `develop` → `feature/0.6.0`; root `VERSION` `0.6.0`; ruff/mypy/pytest
  configuration scoped to `scripts/ci/`; a README naming this repo's single concern.
- **Terraform as content (`T-I.3`).** Seven root stacks and four modules copied with
  **identical** `backend "s3"` keys and identical resource addresses. `prd/03_iam` is not
  copied: it declares no resource, and its state key is removed in the same task that
  proves the rest plan clean. Lock files travel; `required_providers` are untouched.
- **The consumer half of the artifact seam (`T-I.4`).** `prd/06_lambda` and
  `dev/02_lambda` take `layer_s3_key`/`layer_sha256` and the handler equivalents as
  variables resolved by `scripts/ci/resolve_layer.sh` against the contract of K3. No
  `archive_file` over a working-tree path survives — the source tree is in the other repo.
- **Bootstrap repoint (`T-I.6`..`T-I.9`, ADR-4).** A `github_repo` variable replaces the
  hard-coded repository in the four deploy roles' trust `sub` conditions; a fifth role,
  `…-gha-artifacts-publish`, is added with exactly four S3 actions on one bucket and the
  project permissions boundary. Security review precedes the apply; the apply is the
  operator's (the sole documented exception of ADR-6); `publish_oidc_vars.sh` then
  publishes the four variables into this repository.
- **Artifacts bucket + absorbed deferrals (`T-I.10`).** `<artifacts-bucket>` in
  `prd/04_peripherals` — versioned, private, all public access blocked — applied together
  with the Lambda log-group imports and the Terraform-path schedule disable, closing
  v0.5.0's `T-B.14` and `T-B.7` in one apply.
- **Databricks UC by import (`T-I.11`, `T-I.12`, ADR-5).** Inventory first
  (`databricks storage-credentials list`, `external-locations list`, `catalogs list`),
  then a stack declaring exactly what exists, then `terraform import` per object, then a
  plan that must read `No changes`. DLT pipelines, jobs and dashboards are **not**
  imported — they remain DABs.
- **CI rewrite (`T-I.13`, `T-I.14`).** Six infrastructure workflows, re-authored rather
  than copied, keeping the v0.5.0 posture (SHA-pinned actions, `persist-credentials:
  false`, runner hardening, actionlint + zizmor, per-environment concurrency, `-lock=false`
  on the read-only plan path). `stack_map.json` names the surviving stacks only. The four
  security LOW guards of SPEC I8 land in this rewrite, each with a test.

**Verification.** `terraform fmt -check -recursive` + `validate`; per-stack fresh-clone
plan under OIDC; `aws iam get-role`/`get-role-policy`/`simulate-principal-policy` on all
five roles; `aws s3api head-bucket`/`get-bucket-versioning`/`get-public-access-block`;
`aws scheduler get-schedule`; post-import `terraform plan`; `pytest scripts/ci/tests`;
`actionlint`; `zizmor`. ACs: AC-1..AC-9.

## 4. WS-X — the new `dd-chain-explorer`

**Approach.**

- **Skeleton (`T-X.1`).** Fresh `git init`, same branch law, `VERSION` `0.6.0`, a lean
  root `pyproject.toml` (ruff + mypy + pytest for this tree only), a Makefile of thin
  wrappers over the scripts CI runs, and a **new** README — the legacy README described a
  repository that no longer exists.
- **Content migration (`T-X.3`, `T-X.4`).** `apps/dabs/` (7 bundles), `apps/lambda/`,
  `utils/`, `tests/`, the two runbooks and `scripts/build_lambda_layer.sh`, copied as
  content. Bundle content is unchanged except the workspace-host and service-principal
  wiring the new repository's secret names require — a rename, not a redesign.
- **The producer half of the artifact seam (`T-X.5`, ADR-3).** CI builds the layer
  (`--require-hashes -r requirements.lock` for third-party deps plus `pip install ./utils
  --no-deps` as a **path** requirement — the path install is what closes dependency
  confusion) and both handler zips, uploads each to its content-addressed key assuming
  **only** `…-gha-artifacts-publish`, and emits the `<sha256>` values as run outputs per
  K3's contract.
- **Explorer CI (`T-X.6`).** Quality gate, the publish job, `databricks bundle validate`
  per bundle per target, and the DABs deploy lane behind the informed environment gate.
  No Terraform workflow exists here, and the repository holds no role that can mutate
  infrastructure — AC-6b proves that negatively.
- **Bundles live (`T-X.7`).** Validate in `dev` and `hml`, deploy, then diff every
  deployed pipeline's exported notebook against its file in the **new** repo. The `prod`
  target stays guarded by a host variable with no default.

**Verification.** `ruff format --check`, `ruff check`, `mypy`, `pytest
-p no:cacheprovider`, `pip-audit -r`; the publish job log + `aws s3api list-objects-v2`;
`databricks bundle validate -t {dev,hml,prod}`; notebook export diff; `cat VERSION` across
both repos. ACs: AC-10..AC-15.

## 5. WS-L — laws, `AGENTS.md`, cross-repo documentation

**Approach.** Three documents and one amendment, each written once and referenced
everywhere else.

- `T-L.1` — the infrastructure repo's scoped `AGENTS.md` states ADR-6's law normatively
  and names `services/prd/00_bootstrap` as its **sole** exception, with the reason (the
  bootstrap paradox: CI cannot create the roles it needs to authenticate). A CLI mutation
  outside that exception is a defect to register, not a shortcut to take.
- `T-L.2` — the explorer repo's scoped `AGENTS.md` states the mirror: no infrastructure is
  declared here; this is the spec-context main repo, `specs/` is authoritative here; the
  repository is PUBLIC, so nothing that is not public-grade may be committed.
- `T-L.3` — the cross-repo contract doc, authored **first** because K3 depends on it:
  artifact bucket, prefixes, content-addressed key shape, publisher, resolver, the
  five-role OIDC map with the repository each trusts, and the Databricks split.
- `T-L.4` — `specs/constitution.md` amended in the legacy repo **before** C-DAY, so it
  travels already correct.

**Verification.** Read-through against AC-16..AC-18; every migrated runbook grepped for a
stale repository reference.

## 6. WS-V — validation, cutover, gates

**Approach.**

- `T-V.1`..`T-V.3` are the equality proofs of §1.1: green CI in both repos, fresh-clone
  0-diff across every stack, UC + bundle validation with deployed-equals-repo.
- `T-V.4` is **C-DAY** and is executed as one atomic step (O-6/O-7): with both repos green
  and the manifest verified, the whole `specs/` tree — `_archive/` included — is copied
  into the new explorer repo and committed; `diff -r` against the legacy tree must be
  empty; from that commit the legacy `specs/` tree is FROZEN. `T-V.5` writes the legacy
  repo's single remaining commit: a tombstone `README` pointing at both successors.
- `T-V.6`..`T-V.9` are the release gates, all executed **in the new explorer repo**:
  alpha-1 qa review, the rc trio in both repositories, then ship — memory update →
  CLOSURE → archive → the two `develop` → `main` PRs, CI watched to green.
- The whole-tree secret scan (AC-22) runs in `T-V.3` and again immediately before the
  PUBLIC flip, because the tree changes in between.

**Verification.** Both repos' PR check sets; the committed manifest checklist;
`diff -r` of the two `specs/` trees; `dadaia specs doctor` in the new repo; the qa / code
/ security handoffs. ACs: AC-19..AC-24.

## 7. WS-D — legacy decommission (OPERATOR-ONLY)

No task in this workstream is agent-executable. Ordered by O-9: credential cleanup on the
legacy repo (nothing there may still be able to deploy) → the operator's own validation →
the infrastructure repo's PRIVATE → PUBLIC flip, gated on a clean secret scan → deletion
of `dd_chain_explorer`. An agent that finds itself about to run any of these steps has
misread the release.

## 8. Technical risks (beyond SPEC §9)

| Risk | Handling in this plan |
|---|---|
| A backend key or resource address is silently altered in the copy, so the new repo's plan wants to **create** what already exists | `T-V.2` accepts only `0 to add, 0 to change, 0 to destroy` per stack from a **fresh clone**. A non-zero `add` count is a stop-the-line event, not a diff to reconcile by applying |
| The UC import partially succeeds, leaving a stack that half-owns live objects | `T-I.12` imports object by object and re-plans after each; a failure escalates with the partial state recorded, and the fallback is to remove the resource block, never to create the object |
| The artifact seam is written twice with two key shapes | K3: the contract doc precedes both implementations; `T-V.2` fails if the resolver cannot find what the publisher wrote |
| CI is green in each repo separately but the seam is untested end to end | `T-V.2` runs the Lambda-stack plan **after** a real publish from the explorer repo's CI — never against a hand-uploaded object |
| The specs handover races another specs write | K5/O-7: `T-V.4` is a critical section; `T-L.4` is its last predecessor and `T-V.6` its first successor |
| A migrated test quietly disappears | K6/O-8: `T-V.1` asserts the union of the two repos' suites equals the v0.5.0 set; any subtraction needs a `qa-engineer` verdict |

## 9. Rollback

| Step | Rollback |
|---|---|
| Bootstrap repoint (`T-I.8`) | Re-apply `00_bootstrap` with `github_repo` set back to the legacy repository; the legacy repo's CI works again immediately. One variable, one apply |
| Artifacts bucket + Lambda rewire (`T-I.10`) | The bucket is additive; the rewire is a revert of the two stack files. Nothing is destroyed |
| UC import (`T-I.12`) | `terraform state rm` per imported object — the live objects are untouched by an import, which is precisely why ADR-5 forbids recreation |
| DABs deploy from the new repo (`T-X.7`) | Re-deploy from the legacy tree while it still exists (before the operator's deletion), or from the new repo at the previous commit |
| C-DAY (`T-V.4`) | The legacy `specs/` tree still exists, byte-identical, until the operator deletes the repository. Rollback is re-freezing the new tree and un-freezing the old |
| WS-D (deletion, PUBLIC flip) | **No rollback.** This is why O-9 puts them last, behind the ship gate and the operator's explicit validation |

## 10. Assumption on the workspace multi-repo spec-context feature

The structure assumes it: the new `dd-chain-explorer` is the spec context's **main repo**
holding `specs/`; `dd-chain-infrastructure` is an associated repo with no `specs/` tree of
its own; a bug found while working in the infrastructure repo is registered in the main
repo's ledger. **Nothing in this release blocks on that feature landing.** If it has not
landed by C-DAY, the new explorer is an ordinary single-repo spec context and the
infrastructure repo is simply outside any context — the migration completes either way and
no task changes. Should the feature land mid-release, adopting it is a configuration
change, not a re-plan.
