---
slug: cicd-pipeline
title: CI/CD Pipeline
category: ops
tldr: Plan-as-detector Terraform lanes (account → dev → prd, gated by the production environment), an event chain across the three repos through GitHub App dm-chain-explorer-ci, a one-time trust seed, and a rebuild drill — zero manual steps beyond seed, approvals and the drill dispatch.
summary: The control plane of all three repositories after release v0.7.0 (R22, R26, R33, R35). Infra deploy_cloud_infra.yml plans every stack of scripts/ci/stack_map.json with -detailed-exitcode on each develop push and applies only on exit 2 — account and prd groups wave by wave behind the production approval, dev stack by stack without approval; plan-on-PR and weekly drift cover every map stack through one matrix. The chain runs infra dev apply → explorer bundle deploy → capture_run Fargate tasks → file arrival → e2e-verify, linked by repository_dispatch with App tokens. The trust seed (S1-S3) is the only manual apply; the rebuild drill proves the dev workspace is disposable. Status 2026-09-23 — plan-driven lanes live on infra develop; the rest decided and coded.
tags:
  - cicd
  - github-actions
  - terraform
  - oidc
  - github-app
  - chain
last_updated: "2026-09-23"
release_origin: v0.7.0
---

## Propósito

**Status 2026-09-23.** LIVE on infra `develop` (PR-α #10): plan-as-detector lanes, the
temporary `retire` job, bootstrap delta 2. Known defect: the prd lane inherits the skip of
`account-apply` (run `35817189275`), fix PR #11 open. DECIDED, coded, not merged: the
account/workspace/UC/GitHub stacks in the lanes, `signal-explorer`, `capture_run.yml`, the
trust seed (infra PR-β); explorer chain CI (PR #5). Not yet written: `rebuild_drill.yml`.

Every cloud change reaches the cloud through CI applying Terraform, and every cross-repo
step is an event — no hand command, no PAT, no git-diff detection.

| Repo | Workflows |
|---|---|
| infra | `deploy_cloud_infra.yml` (+ reusable `gated_wave.yml`), `plan_on_pr.yml` (+ `stack_plans.yml`), `drift_detection.yml` (Mon 06:00 UTC), `destroy_cloud_infra.yml`, `destroy_all_cloud_infra.yml`, `capture_run.yml`, `scorecard.yml` |
| explorer | `ci.yml`: quality, `validate-dev` (PR), `deploy-dev`, `validate-prod` (`production`), `signal-infra`, `e2e-verify` |
| capture | `publish-images.yml` (push `develop`/`main`) |

## Fluxo de uso

| Step | Trigger | Job |
|---|---|---|
| 1 | push `develop` (infra) or dispatch | branch guard → OIDC preflight → account waves (gated) → `dev-deploy` → prd waves (gated) |
| 2 | step 1 dev green | `signal-explorer` → `repository_dispatch infra-dev-applied` |
| 3 | push `develop` or `infra-dev-applied` (explorer) | `deploy-dev` (`bundle deploy -t dev`) → `signal-infra` → `explorer-dev-deployed` |
| 4 | `explorer-dev-deployed` (infra) | `capture_run`: one Fargate Spot task per run job, wait, exit 0 + manifest → `capture-landed` |
| 5 | file arrival | job `[dev] dm-market-data` |
| 6 | `capture-landed` (explorer) | `e2e-verify`: FILE_ARRIVAL run succeeded, every gold table > 0 rows, 0 sha rejections |

- **Plan as detector:** every map stack `plan -detailed-exitcode`; apply on exit 2 only. A
  gated wave plans, shows the summary (destroys included) at the `production` approval,
  applies that wave, then plans the next.
- **Trust seed** (`scripts/seed/trust_seed.sh`, `docs/runbooks/trust-seed.md`, operator
  terminal, reads before it writes, run 2 changes nothing, no secret in argv/output): S1
  AWS state bucket + bootstrap + OIDC vars + BPA; S2 GitHub App secrets + `production`
  env; S3 account SP secret + metastore check.
- **Rebuild drill** (`rebuild_drill.yml`, dispatch, env `dev`, AC-29): snapshot tables →
  destroy `dev/05_workspace` → dev lane → explorer redeploy → compare counts → capture run.

## Trigger típico

Consulted for any workflow, stack-map, role, secret-name or chain-event change, and before
asking a human to do anything by hand (a new hand act is an M-step, never a default).

## Diferencial

The plan decides what applies, so no hand-kept file list can drift; each repo learns of the
previous step by an event, so the whole chain runs from one `develop` merge with approvals
as the only human acts. Secrets are written by Terraform from account/workspace outputs.

## Estado runtime tocado

- `scripts/ci/stack_map.json` — groups `account`/`dev`/`prd`, `upstreams` (waves),
  `gated`, `operator_only`, `never_destroy`
- Workflow `env: AWS_REGION: us-east-1` + `TF_VAR_aws_region` (pinned equal by test);
  Terraform 1.10.5
- Repo variables `AWS_DEPLOY_ROLE_{DEV,PRD,READONLY}`, capture `AWS_CAPTURE_PUBLISH_ROLE`
  (published by `publish_oidc_vars.sh`); App credentials `CI_APP_*`; infra secrets
  `DATABRICKS_ACCOUNT_ID/_CLIENT_ID/_CLIENT_SECRET` (seed S3)
- GitHub environments `dev`, `production` in the three repos ([[environments]])

### Postura de segurança da esteira

- OIDC only, job-scoped `id-token: write`; roles capped by a boundary with self-mutation
  deny; `prd/00_bootstrap` is never applied by CI.
- App tokens minted per job (`actions/create-github-app-token`), one repo, least
  permissions (signal jobs `contents: write`); the private key never leaves its secret.
- Every action SHA-pinned, runner hardening, `persist-credentials: false`; `actionlint` +
  `zizmor` clean; no loop (`capture_run` never signals infra); `concurrency` per lane.

## Dependências

- **[[aws-resources]]** — the stacks and roles
- **[[medallion-pipelines]]**, **[[capture-layer]]** — what the chain deploys and runs
- **[[quality-assurance]]** — the contract tests that pin this shape

## Referência

### Retirado do inventário

`changed_stacks.py`/`detect_changes.sh` git-diff detection, `FORCE`, `force_apply`,
`destroy_ack`, the bundle filter, `publish-artifacts.yml`, `resolve_*.sh`,
`tf_state_lock_check.sh`, the `raw/` object-count drift check, `deploy_all_dm_applications.yml`,
the `hml` lane and `00-bootstrap-apply.md` (after PR-β). The `retire` job dies in the
region-move commit.
