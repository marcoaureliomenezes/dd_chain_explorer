# Runbook — CI/CD security posture (public-repo hardening)

**Source:** public-repo CI security audit, 2026-08-23 (security-reviewer). This runbook
records the software-engineer-owned remediations applied to `.github/workflows/**` and
`scripts/ci/**`. Repo-settings-only findings (environment protection rules, branch
protection, Actions allow-list, Dependabot toggles) are operator actions and are not
repeated here.

## F-01 — never upload the `tfplan` binary as a public artifact

**Why this mattered.** `terraform plan -out=tfplan` writes a binary plan file that
contains every referenced value in plaintext, including `TF_VAR_*` secrets (e.g.
`DATABRICKS_UC_EXTERNAL_ID`) — Terraform's `sensitive = true` only redacts *display*
output, never the plan/state contents
(<https://developer.hashicorp.com/terraform/tutorials/configuration-language/sensitive-variables>).
GitHub Actions artifacts of a public repository are downloadable by **anyone with read
access to the repo** — i.e. everyone
(<https://docs.github.com/en/rest/actions/artifacts>). Uploading `tfplan` therefore
published the plaintext secret to the world for the life of the artifact's retention
window.

**What changed.**

- `scripts/ci/plan_env.sh` no longer stages the `tfplan` binary under
  `$PLAN_ARTIFACT_DIR/<stack-id>/` — it stages **only** the redacted `plan.txt` text
  summary that `terraform plan -no-color` already produces (via `scripts/ci/tf_plan.sh`).
- `.github/workflows/deploy_cloud_infra.yml`'s `prd-plan` / `hml-plan` jobs upload
  `path: .plan-artifacts/**/plan.txt` (never a glob that could pick up a `tfplan` file)
  with `retention-days: 1` (down from 7).
- `scripts/ci/deploy_env.sh`'s apply phase (`prd-apply` / `hml-apply`) **never** consumes
  a saved plan binary. Every stack is now unconditionally re-planned locally, under the
  environment-gated deploy role, and the fresh plan is compared against the downloaded
  approved `plan.txt` via the existing divergence guard,
  `scripts/ci/plan_gate_check.sh plan-diff` (ADR-R6-5) — this guard already compared
  sorted resource-address + action sets and add/change/destroy counts, so no new script
  was needed; it is now the *only* path (previously it only ran for stacks downstream of
  an in-run upstream change). A divergence, or a missing approved summary for a
  non-deferred stack, still fails the run closed (exit 3) with a published diff.

**Operator follow-up (tracked separately, not software-engineer scope):** rotate
`DATABRICKS_UC_EXTERNAL_ID` and delete any pre-existing `hml-saved-plans` /
`prd-saved-plans` artifacts that still carry a `tfplan` binary from before this fix
(`gh api -X DELETE repos/<org>/<repo>/actions/artifacts/<id>`).

## F-04 — `id-token: write` at job scope only

Workflow-level `permissions:` in `deploy_all_dm_applications.yml`,
`deploy_cloud_infra.yml`, `destroy_all_cloud_infra.yml`, `destroy_cloud_infra.yml`, and
`drift_detection.yml` is now `contents: read` only. `id-token: write` is granted solely
on the jobs that call `aws-actions/configure-aws-credentials` (matching the pattern
`plan_on_pr.yml` already used).

## F-06 — commit-SHA pins + Dependabot

`aws-actions/configure-aws-credentials` was pinned to `ff717079…`, the SHA of the
**annotated tag object** for the floating `v4` tag — not a commit SHA. It is now pinned
to `7474bc4690e29a8392af63c5b98e7449536d5c3a` (`v4.3.1`'s actual commit, verified via
`gh api repos/aws-actions/configure-aws-credentials/git/ref/tags/v4.3.1` →
`git/tags/<sha>`). The other 6 third-party actions were refreshed the same way, to each
action's current stable release, always resolving through `git/ref/tags/<tag>` and, when
the ref is an annotated tag object, dereferencing to the underlying commit:

| Action | Was | Now |
|---|---|---|
| `actions/checkout` | v4.3.1 | v7.0.1 |
| `actions/setup-python` | v5.6.0 | v7.0.0 |
| `hashicorp/setup-terraform` | v3.1.2 | v4.0.1 |
| `databricks/setup-cli` | v0.218.0 | v1.13.0 |
| `actions/upload-artifact` | v4.6.0 | v7.0.1 |
| `actions/download-artifact` | v4.1.8 | v8.0.1 |

Every input each workflow actually sets (`fetch-depth`, `persist-credentials`,
`python-version`, `terraform_version`, `terraform_wrapper`, `name`, `path`,
`retention-days`, `if-no-files-found`) was confirmed present and unchanged in the new
release's `action.yml` before pinning. `.github/dependabot.yml` now tracks
`github-actions` (repo root) and `pip` (`apps/lambda/`) weekly so pins stay current
automatically going forward.

## F-07 / F-09 / F-10 / F-11 / F-12 — NOT YET IMPLEMENTED (deferred, this session)

Only F-01, F-04 and F-06 above landed in this session (commits `51d579a`, `97603f5`,
`bc41801` on `feature/0.5.0`). The remaining items from the audit's ordered remediation
list are still open and are tracked here so the next session picks up exactly where
this one stopped — do not assume any of the following is done:

- **F-07** — `deploy_all_dm_applications.yml`'s Databricks credential selection still
  uses the `cond && secretA || secretB` ternary against `DATABRICKS_PROD_HOST` /
  `DATABRICKS_HML_HOST` / `DATABRICKS_DEV_HOST` / `DATABRICKS_PROD_TOKEN` /
  `DATABRICKS_HML_TOKEN` / `DATABRICKS_DEV_TOKEN` (`deploy_all_dm_applications.yml:211-212`)
  — several of those secrets are undefined at the repo level today (drift, F-08). This
  needs environment-scoped `DATABRICKS_HOST`/`DATABRICKS_CLIENT_ID`/
  `DATABRICKS_CLIENT_SECRET` (OAuth M2M) created by the operator as environment secrets
  first, then the workflow/`deploy_all.sh` wiring updated to read them directly with a
  fail-closed non-empty assertion.
- **F-09** — the 4 interpolated inputs (`inputs.confirm`, `inputs.target`,
  `github.event.inputs.full_destroy`, `github.base_ref`) still substitute directly into
  `run:` blocks; not yet routed through `env:`.
- **F-10** — no `actions/checkout` step yet sets `persist-credentials: false`; the
  `prd-create-tag` job in `deploy_cloud_infra.yml` still does `git fetch origin master` /
  `git checkout master` (should be `main`).
- **F-11** — no `configure-aws-credentials` step yet sets `role-session-name` /
  `mask-aws-account-id: true`; the `aws sts get-caller-identity` evidence steps still
  print the full, unmasked account id + role ARN to public logs.
- **F-12** — no `step-security/harden-runner` step exists in any workflow; no `zizmor`
  step runs inside CI (`quality` job); `.github/workflows/scorecard.yml` does not exist.

Repo-settings-only findings (F-02, F-03, F-05, F-08, F-13) remain entirely with the
operator, as noted at the top of this runbook.
