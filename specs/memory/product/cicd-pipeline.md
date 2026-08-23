---
slug: cicd-pipeline
title: CI/CD Pipeline
category: ops
tldr: Seven GitHub Actions workflows deploying Terraform, Lambdas and DABs under OIDC-only auth — operational end to end.
summary: "Describes the CI/CD control plane: the seven workflows, the dependency-aware informed gate (pre-gate plan artifacts, re-plan at apply, fail-closed divergence), the OIDC-only authentication model built on the operator-applied prd/00_bootstrap stack and its four short-lived roles with a permissions boundary, the fail-fast role-variable preflight, the quality gate (ruff, mypy, three pytest suites, pip-audit, actionlint, terraform fmt/validate), the runner-hardening posture, the scripts/ci toolbox driven by stack_map.json, and the repository governance — main as default and protected branch, protected develop, environment reviewers and deployment-branch policies."
tags:
  - cicd
  - github-actions
  - terraform
  - oidc
  - deploy-gate
last_updated: "2026-08-23"
release_origin: v0.5.0
---

## Propósito

The CI/CD pipeline is the control plane for every infrastructure and application change.
Infrastructure reaches AWS through it and through no other path. Seven workflow files
live on `main`:

| Workflow | Purpose |
|---|---|
| `plan_on_pr.yml` | quality gate + read-only `fmt`/`validate`/`actionlint` + per-stack Terraform plan on pull requests into either long-lived branch |
| `deploy_cloud_infra.yml` | the informed, gated, per-stack Terraform apply path |
| `destroy_cloud_infra.yml` | targeted destroy of one environment or stack |
| `destroy_all_cloud_infra.yml` | full teardown, ordered across environments, covering every live stack |
| `deploy_all_dm_applications.yml` | application lane — Lambda deploys and Databricks Asset Bundles |
| `drift_detection.yml` | scheduled read-only plan across every stack |
| `scorecard.yml` | OpenSSF Scorecard supply-chain scoring of the repository |

The apply model is **informed and gated**: every plannable stack uploads its plan text as
a short-retention artifact and writes an add/change/destroy summary to the run summary
*before* the environment gate. After the gate, every stack is **re-planned** and the run
fails closed on any divergence from the approved summary, publishing the diff — the plan
that applies is always the plan a human approved. Destroy-containing plans require an
explicit acknowledgment input. Stacks that cannot be planned pre-gate are listed as
deferred, never silently skipped.

Authentication is **OIDC-only**. Each AWS-touching job requests `id-token: write` at job
scope and assumes one of four roles — dev deploy, hml deploy, prd deploy, read-only plan
— whose ARNs are published as repository variables. The roles live in the
operator-applied `prd/00_bootstrap` stack that CI never applies: they are prefix-scoped
to project resources, capped by a permissions boundary, and carry an explicit `Deny` on
self-mutation (`iam:*` against `dm-chain-explorer-gha-*`) and on the user-credential verbs.
No static AWS access key exists anywhere in the repository or its secret store.

## Fluxo de uso

1. A pull request into `develop` or `main` runs the quality gate — `ruff format --check`,
   `ruff check`, `mypy`, the repo-level `tests/` suite, the `scripts/ci/tests` suite and
   `pip-audit` over the pinned lock — plus `actionlint`, `terraform fmt -check` and
   `validate`.
2. The role-variable **preflight** runs first in every role-assuming job: an empty
   `vars.AWS_DEPLOY_ROLE_*` fails the job immediately with an explicit message, instead of
   failing opaquely inside `configure-aws-credentials`.
3. The change detector plus `changed_stacks.py` resolve affected stacks from
   `scripts/ci/stack_map.json` — the single source for the stack list, module map and
   upstream ordering. A missing merge base fails loudly rather than falling back.
4. Plan runs under the read-only role with `-lock=false`, so the plan path needs no
   lock-table write; each plannable stack publishes its plan text and summary.
5. The approver reviews that summary at the `hml` or `production` environment gate.
6. Post-gate apply runs in dependency order, re-planning each stack and failing closed on
   divergence. `dev` keeps an automatic per-stack flow.
7. The application lane builds the Lambda layer from source, uploads it to the artifact
   bucket at a content-addressed key, passes `layer_s3_key`/`layer_sha256` into the Lambda
   stacks, then deploys the Databricks bundles.

## Trigger típico

Fires on every pull request into a long-lived branch, on every infrastructure deploy or
destroy dispatch, on every application release, and on the drift-detection schedule.

## Diferencial

Before the rebuild, the pipeline was written but could not authenticate: no OIDC role
existed and no role variable was published, so every AWS job was decorative. Now the
bootstrap paradox is designed away — the roles live in a stack CI never applies, published
by a checked-in script, and a preflight makes a missing variable a loud, one-line failure.
The informed gate shows the approver exactly what will change per stack and guarantees the
applied plan is the approved plan; protected branches mean the pull request that ships
cannot bypass the gate; and least-privilege roles give each environment its own blast
radius with self-escalation explicitly denied.

## Estado runtime tocado

- `.github/workflows/` — the seven workflow files; `.github/dependabot.yml`
- `scripts/ci/` — the Bash helpers, `changed_stacks.py`, `stack_map.json`,
  `publish_oidc_vars.sh` and the `tests/` suite
- GitHub environments `dev`, `hml`, `production` — reviewer and deployment-branch policies
- GitHub repository variables `AWS_DEPLOY_ROLE_{DEV,HML,PRD,READONLY}`; the secret store
  holds Databricks credentials only
- Branch protection on `main` and `develop`
- Remote Terraform state bucket and its lock table
- Run artifacts: per-stack plan text and divergence diffs, 1-day retention

### Postura de segurança da esteira

- Every action reference is pinned to a 40-character commit SHA; the allowed-actions
  policy is an allowlist of GitHub-owned, verified and explicitly pinned patterns.
- Every job runs under a runner-hardening step in audit mode, and checks out with
  `persist-credentials: false`.
- `id-token` is granted per job, never workflow-wide; `zizmor` reports no high-severity
  finding on the workflow set.
- Plan artifacts carry plan **text** only, never the binary plan, with 1-day retention.
- Every workflow declares a per-environment `concurrency` group, and deploy and destroy of
  the same environment share it, so two dispatches cannot race the same remote state.
- The Terraform version is single-sourced and matched by an exact `required_version`; the
  `actionlint` installer is pinned by version and checksum.

### Governança do repositório

`main` is the default branch. It requires a pull request and nine passing status checks
(quality gate, preflight, change detection and the six per-stack plans), is strict, and
allows neither force-push nor deletion. `develop` allows neither force-push nor deletion.
The `hml` and `production` environments require the operator as reviewer; all three
environments carry a deployment-branch policy limited to `develop` and `main`. Pull
requests from forks require approval before any workflow runs. No `hml-apps` environment
exists or is referenced.

Drift detection is enabled on the default branch; its first scheduled run is pending.

## Dependências

- **`prd/00_bootstrap`** ([[aws-resources]]) — the operator-applied stack holding the four
  OIDC roles and the CI permissions boundary; `publish_oidc_vars.sh` reads its outputs to
  publish the repository variables
- **Terraform stacks** under `services/` — the subjects of plan and apply
- **Downstream**: [[medallion-pipelines]] and [[serving-layer]] — Databricks Asset Bundles
  and dashboards ship through the applications workflow
- **Verified by**: [[quality-assurance]] — the CI-script suite is the automated proof that
  the gate logic behaves, and it runs on every pull request
