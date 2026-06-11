---
slug: cicd-pipeline
title: CI/CD Pipeline
category: ops
tldr: GitHub Actions control plane — 7 workflows, informed environment gate with saved-plan apply, OIDC role-assumption, scripts/ci toolbox, single-source stack map.
summary: Describes the CI/CD control plane after the v0.3.0 gate redesign — the 7 GitHub Actions workflows, the dependency-chain-aware informed environment gate (pre-gate plan artifacts, saved-plan apply, fail-closed re-plan divergence), the 4-role OIDC trust matrix, and the scripts/ci helper toolbox driven by stack_map.json.
tags:
  - cicd
  - github-actions
  - terraform
  - oidc
  - deploy-gate
agent_tier: self-pull
token_estimate: 700
last_updated: "2026-06-11"
release_origin: v0.3.0
---

## Propósito

The CI/CD pipeline is the control plane that plans, gates, and applies every
infrastructure and application change. Seven GitHub Actions workflows cover the full
lifecycle: `deploy_cloud_infra.yml`, `destroy_cloud_infra.yml`,
`destroy_all_cloud_infra.yml`, `deploy_all_dm_applications.yml`, `plan_on_pr.yml`,
`drift_detection.yml`, and `auto-bump-version.yml`.

Production and HML infrastructure applies are **informed, gated, per-stack-signaled**
operations: every plannable stack's plan is uploaded as an artifact and summarized
(add/change/destroy counts) BEFORE the environment gate, and the post-gate apply uses
the saved approved plan binary. Stacks that cannot be planned pre-gate (declared
`bootstrap_plannable: false`, e.g. prd `05b_databricks_workspace`) are listed as
deferred to post-upstream stage — never silently skipped.

CI authenticates to AWS exclusively via GitHub OIDC role-assumption (4 IAM roles in the
account-level `services/prd/03_iam` stack): dev deploy (`environment:dev`), hml deploy
(`environment:hml` + reviewer-less `environment:hml-apps`), prd deploy
(`environment:production`), and a read-only plan role (`pull_request` + default-branch
ref claims) used by PR plans, drift detection, and `all-check-infra`. No static AWS
keys exist in any workflow.

## Fluxo de uso

1. A push/dispatch triggers the deploy workflow; `scripts/ci/detect_changes.sh` +
   `changed_stacks.py` resolve affected stacks from `scripts/ci/stack_map.json`
   (single source for stack list, module map, upstream dependencies — a missing
   merge-base fails loudly, no `HEAD~1` fallback).
2. Pre-gate plan phase: each plannable stack uploads its `tfplan` binary + full
   `plan.txt` artifact; a consolidated add/change/destroy summary is written to the run
   summary before the environment gate.
3. The approver reviews the summary at the informed environment gate
   (`hml`/`production`); destroy-containing plans require an explicit acknowledgment
   input enforced by `scripts/ci/plan_gate_check.sh`.
4. Post-gate apply in dependency order (`scripts/ci/deploy_env.sh`): a stack whose
   upstreams applied no in-run changes applies its saved approved plan; a stack
   downstream of an in-run upstream apply is re-planned and the run FAILS CLOSED
   (exit != 0, diff published as artifact + job summary) on any divergence from the
   approved summary — re-approval is the normal gate of the operator-re-triggered run.
5. `dev` keeps its automatic per-stack flow; `plan_on_pr.yml` and
   `drift_detection.yml` run read-only under the plan role.

## Trigger típico

Every PR (plan + fmt/validate gate), every dev/hml/prd infrastructure deploy or
destroy, every application release run, scheduled drift detection, and version bumps.

## Diferencial

Before v0.3.0 a single blind environment approval unleashed a loop of
`terraform apply -auto-approve` with silently masked failures. The informed gate makes
the approver see exactly what will change per stack, guarantees the applied plan is the
approved plan (or fails closed on divergence), and the OIDC model removes the standing
static-key secret with per-environment blast radius. `actionlint` (all workflows),
`terraform fmt -check`/`validate`, `timeout-minutes` on every job, and `concurrency:`
groups (`cancel-in-progress: false`) keep the surface deterministic.

## Estado runtime tocado

- `.github/workflows/` — the 7 workflow files
- `scripts/ci/` — 18 Bash helpers + `changed_stacks.py` + `stack_map.json`
- GitHub environments: `dev` (auto), `hml` (required_reviewers — operator-pending),
  `hml-apps` (reviewer-less by design), `production`
- GitHub repo vars `AWS_DEPLOY_ROLE_{DEV,HML,PRD,READONLY}` (role ARNs)
- S3 `dm-chain-explorer-terraform-state` + DynamoDB lock table (plan/apply state)
- Run artifacts: per-stack `tfplan` + `plan.txt` + divergence diffs

## Dependências

- **AWS GitHub OIDC identity provider** (`token.actions.githubusercontent.com`) —
  created once by the operator (OP-R6-2), referenced by trust policies via ARN
- **4 OIDC IAM roles** in `services/prd/03_iam` ([[aws-resources]]) — first apply rides
  the bootstrap static-key path, then cutover
- **Terraform stacks** under `services/` — the subjects of plan/apply
- **Downstream**: [[capture-layer]] images/services and [[medallion-pipelines]] DABs
  deployments ship through `deploy_all_dm_applications.yml`
