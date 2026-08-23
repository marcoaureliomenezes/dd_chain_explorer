---
slug: cicd-pipeline
title: CI/CD Pipeline
category: ops
tldr: Seven GitHub Actions workflows with an informed environment gate, saved-plan apply and OIDC role-assumption — fully written but inert since April 2026.
summary: "Describes the CI/CD control plane — the seven workflows, the dependency-aware informed gate (pre-gate plan artifacts, saved-plan apply, fail-closed divergence), the OIDC role-assumption model, the scripts/ci toolbox driven by stack_map.json, and the GitHub environments. Records the gaps that make it non-operational today: the OIDC role variables do not exist and the roles were never applied, the applications workflow still provisions the retired capture lane, the CI-script tests never run, no provider lock files are committed, and neither long-lived branch is protected."
tags:
  - cicd
  - github-actions
  - terraform
  - oidc
  - deploy-gate
last_updated: "2026-08-23"
release_origin: v0.4.0
---

## Propósito

The CI/CD pipeline is the intended control plane for every infrastructure and application change. Seven GitHub Actions workflow files live on the development branch:

| Workflow | Purpose |
|---|---|
| `plan_on_pr.yml` | read-only `fmt`/`validate`/`actionlint` + per-stack Terraform plan on pull requests |
| `deploy_cloud_infra.yml` | the informed, gated, per-stack Terraform apply path |
| `destroy_cloud_infra.yml` | targeted destroy of one environment or stack |
| `destroy_all_cloud_infra.yml` | full teardown, ordered across environments |
| `deploy_all_dm_applications.yml` | application lane — Databricks Asset Bundles and Lambda deploys |
| `drift_detection.yml` | scheduled read-only plan across every stack |
| `auto-bump-version.yml` | version bump on merge into the development branch |

The apply model is **informed and gated**: every plannable stack uploads its plan binary plus full plan text as an artifact and writes an add/change/destroy summary to the run summary *before* the environment gate; the post-gate apply consumes the saved, approved plan. A stack downstream of an in-run apply is re-planned and the run **fails closed** on any divergence from the approved summary, publishing the diff. Destroy-containing plans require an explicit acknowledgment input. Stacks that cannot be planned pre-gate are listed as deferred, never silently skipped.

Authentication is designed to be **OIDC-only**: each AWS-touching job assumes one of four roles (dev deploy, hml deploy, prd deploy, read-only plan) via `id-token: write` and a `role-to-assume` value read from a repository variable. Every action reference is pinned to a 40-character commit SHA.

## Fluxo de uso

1. A push or dispatch triggers the deploy workflow; the change detector plus `changed_stacks.py` resolve affected stacks from `scripts/ci/stack_map.json` — the intended single source for the stack list, module map and upstream ordering. A missing merge base fails loudly rather than falling back.
2. Pre-gate plan phase: each plannable stack uploads its plan binary and text; a consolidated summary is written before the gate.
3. The approver reviews that summary at the `hml` or `production` environment gate.
4. Post-gate apply runs in dependency order: an untouched-upstream stack applies its approved plan; a downstream stack is re-planned and the run fails closed on divergence.
5. `dev` keeps an automatic per-stack flow; plan-on-PR and drift detection run read-only under the plan role.

## Trigger típico

Intended to fire on every pull request, every infrastructure deploy or destroy, every application release, weekly drift detection and every merge-driven version bump. In practice none of this currently happens — see below.

## Diferencial

Before the gate redesign, a single blind approval unleashed a loop of auto-approved applies with masked failures. The informed gate makes the approver see exactly what will change per stack, guarantees the applied plan is the approved plan or fails closed, and the OIDC design removes the standing static-key secret while giving each environment its own blast radius. Job timeouts, per-environment concurrency groups and full SHA pinning keep the surface deterministic.

## Estado runtime tocado

- `.github/workflows/` — the seven workflow files
- `scripts/ci/` — 18 Bash helpers, `changed_stacks.py`, `stack_map.json`, and a `tests/` suite
- GitHub environments `dev`, `hml`, `production`
- GitHub repository variables for the four OIDC role ARNs, and the repository secret store
- Remote Terraform state bucket and its lock table
- Run artifacts: per-stack plan binaries, plan text and divergence diffs

### Estado real e lacunas

The control plane described above is **written but not operational**. The last GitHub Actions run of any kind was 2026-04-11; every infrastructure apply since then was performed locally by the operator. All gaps below are recorded in audit `20260823T145726Z-4db47555`.

- **CI cannot authenticate to AWS** (gap — DRIFT-01). Every OIDC step resolves a repository variable for its role ARN, but none of the four variables exists, and the IAM stack that defines those roles was never applied. `configure-aws-credentials` receives an empty `role-to-assume`, so every AWS-touching workflow is non-functional as written.
- **Static AWS keys survive unused** (gap). Long-lived access-key secrets remain in the repository secret store while no workflow references them — a standing credential with no consumer. They must be deleted and the underlying keys rotated.
- **The applications workflow still deploys the retired capture lane** (gap — DRIFT-02). It provisions ephemeral capture queues and stream resources, launches the retired producer services, and destroys a Terraform module that this release deleted. Because the Databricks bundle and Lambda deploys are chained *behind* those steps, the entire application deploy path is broken end-to-end — the retirement was applied to the teardown half only.
- **Environments are unprotected** (gap). `hml` has zero protection rules, so its gate approves itself; only `production` requires a reviewer. A reviewer-less `hml-apps` environment is referenced by nine jobs but does not exist and would be auto-created unprotected on first run. No environment has a deployment-branch policy.
- **No branch protection** on either long-lived branch (gap). Combined with plan-on-PR triggering only for PRs into the development branch, the pull request that actually ships passes through no plan, no format check and no lint.
- **Scheduled drift detection has never fired** (gap). GitHub schedules cron only from the default branch, and the drift-detection workflow does not exist there. The same mechanism leaves plan-on-PR and the version bump unregistered.
- **The CI-script tests never run** (gap). The 45 tests that guard the deploy gate, the destroy acknowledgment and the stack map are executed by no workflow — every guard described above is currently decorative. See [[quality-assurance]].
- **The single-source stack map is not single-source** (gap). The dev stacks declare an empty module list although they do consume shared modules, so a shared-module edit triggers no dev plan; several production entries declare module edges that do not exist; and four other files carry their own hard-coded stack lists.
- **No provider lock files are committed** (gap). With a floating provider constraint, every run resolves the newest provider — a gated apply can execute against a version it was never planned against.
- **The applications workflow declares no concurrency group** (gap), so two dispatches can race the same shared environment and remote state. Deploy and destroy of the same environment also use different groups and can run simultaneously.

## Dependências

- **AWS OIDC identity provider and the four deploy roles** in the account-level IAM stack ([[aws-resources]]) — the roles must be applied and their ARNs published as repository variables before any workflow can authenticate
- **Terraform stacks** under `services/` — the subjects of plan and apply
- **Downstream**: [[medallion-pipelines]] and [[serving-layer]] — Databricks Asset Bundles and dashboards ship through the applications workflow
- **Verified by**: [[quality-assurance]] — the CI-script test suite is the only automated proof that the gate logic behaves
