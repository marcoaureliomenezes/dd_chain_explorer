# PLAN: v0.3.0

**Status:** Em revisão
**Release ID:** v0.3.0
**Phase:** PLAN
**Owner:** product-engineer
**Date:** 2026-06-11

---

## Strategy

Four workstreams in strict macro-order (grill priority table): **WS-A CI safety →
WS-B1 key-logging fix → WS-B2/B3 OIDC → sanitization**, with sanitization runnable in
parallel at any time (fully disjoint write sets: `specs/**` vs `.github/**`+`scripts/**`+
`services/**`+`apps/**`). WS-B3 is hard-sequenced after WS-A because both edit the same
7 workflow files. Operator actions OP-R6-1..4 are tracked but never block agent tasks
except OP-R6-2 → T-R6-B3.

```
WS-A   A1 → A2 → (A3 operator) ; A4,A5,A6,A7,A8 parallel after A1   [devops-engineer]
WS-B1  independent, any time                                         [software-engineer]
WS-B2  terraform roles — parallel with WS-A (different files)        [software-engineer]
WS-B3  workflow OIDC cutover — AFTER WS-A complete + OP-R6-2 done    [devops-engineer]
SAN    S1,S2 → S3 ; S4 ; S5,S6 in CLOSURE memory window              [product-engineer +
                                                                      software-engineer]
```

---

## Layers affected

| Layer | Workstream | Files |
|-------|-----------|-------|
| CI scripts | A1, A5, A8 | `scripts/ci/deploy_env.sh`, `scripts/ci/tf_plan.sh`, `scripts/ci/detect_changes.sh` |
| Workflows | A2, A4, A5, A6, A7, A8, B3 | all 7 files under `.github/workflows/` |
| Terraform | A7 (fmt), B2 (roles) | `services/**` (15 fmt files); `services/{dev,hml,prd}/03_iam/**` |
| Streaming app | B1 | `apps/docker/onchain-stream-txs/src/4_mined_txs_crawler.py` + tests |
| SDD registry | S1–S6 | `specs/bugs/*`, `specs/domains/` → `_archive/`, `specs/memory/*` frontmatter |
| GitHub settings | A3 (operator) | `hml` environment required_reviewers |

---

## Execution order

### Wave 1 — Foundations (parallel)

1. **T-R6-A1** (devops-engineer): rewrite the apply-signal mechanism in
   `deploy_env.sh`/`tf_plan.sh` — per-stack exit-signal, no `$GITHUB_OUTPUT` scraping, no
   silent `/dev/null` skip. This is the substrate for A2.
2. **T-R6-B1** (software-engineer): key-logging fix + log-content unit test.
3. **T-R6-B2** (software-engineer): 4 OIDC IAM roles in terraform (env `03_iam` stacks +
   read-only plan role). Plans reviewed; apply rides the existing deploy path.
4. **T-R6-S1/S2** (PE / SE): bug frontmatter `session_id: null`; rmdir empty
   `configs/`+`schemas/` dirs.
5. **Operator:** OP-R6-2 (OIDC provider), OP-R6-3 (hml required_reviewers) requested at
   wave start so they are ready by Waves 2–3.

### Wave 2 — Gate redesign (after A1)

6. **T-R6-A2** (devops-engineer): two-phase plan→informed-gate→apply for PRD and HML in
   `deploy_cloud_infra.yml` per ADR-R6-4 (artifacts, consolidated summary, destroy
   acknowledgment input, saved-plan apply). Dev path untouched.
7. **T-R6-A4/A5/A6/A7/A8** (devops-engineer, parallelizable): concurrency groups;
   error-masking purge; timeouts; fmt fix + fmt/validate gate; change-detection map +
   loud merge-base failure. A5/A6 edits inside `deploy_cloud_infra.yml` coordinate with
   A2 (same file — single owner, sequential commits).
8. **T-R6-A3** (operator + devops-engineer verify): hml environment gate evidence
   (`gh api repos/:owner/:repo/environments`).
9. **T-R6-S3** (product-engineer): close the 7 verified-fixed bugs with `fixed_in:`
   evidence (re-run each verification command first).
10. **T-R6-S4** (product-engineer, PM/operator runs `git mv`): archive `specs/domains/`
    → `specs/_archive/legacy-domains/<ts>/` and `specs/releases/legacy/` → `_archive/`.

### Wave 3 — OIDC cutover (after WS-A complete + OP-R6-2)

11. **T-R6-B3** (devops-engineer): remove static keys from all 7 workflows;
    `role-to-assume` + `id-token: write`; read-only plan role on `plan_on_pr.yml` +
    `drift_detection.yml`. Validate with a PR plan run + a dev deploy + drift run.
12. **Operator:** OP-R6-4 (retire static keys/secrets) after validation; OP-R6-1 (rotate
    Infura key) any time after B1 deploys.

### Wave 4 — CLOSURE window (memory writes)

13. **T-R6-S5** (product-engineer): token_estimate frontmatter fixes (6 atoms).
14. **T-R6-S6** (product-engineer + ai-engineer): heading-allowlist evaluation — rewrite
    valid cases or file upstream library bug; then close `drift-10` with evidence.
15. CLOSURE.md + tech-stack.md memory update + archive.

---

## Technical risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| A2 gate redesign breaks hml/prd deploy | deploy outage | keep dev path untouched; validate on hml first (it gains the same gate); plan artifacts make failures visible |
| Saved-plan apply hits plan-staleness (`tfplan` older than state) | apply refused | acceptable failure mode — re-run plan phase; document in workflow summary |
| OIDC `sub` claim mismatch (environment vs ref binding) | auth failures at cutover | trust policies bind to GitHub *environments* per ADR-R6-3; test with dev role first |
| Same-file contention A2↔A5/A6↔B3 | merge churn | single owner (devops-engineer), sequential commits, B3 strictly last |
| fmt fix touches 15 files across stacks | noisy diff | mechanical `terraform fmt` only — no semantic edits; reviewed as one commit |
| Bug closures without live re-verification | registry lies | S3 acceptance re-runs each bug's verification command |

---

## Validation plan

| Check | Command | Pass criterion |
|-------|---------|---------------|
| No output scraping | `grep -n 'GITHUB_OUTPUT' scripts/ci/deploy_env.sh` | no `grep`/`tail -1` read path |
| Static keys gone | `git grep -l 'AWS_SECRET_ACCESS_KEY' .github/workflows/` | empty |
| OIDC wired | `git grep -c 'role-to-assume' .github/workflows/` | every AWS-auth job |
| Concurrency | `grep -A2 'concurrency:' .github/workflows/{destroy_all_cloud_infra,auto-bump-version,drift_detection}.yml` | groups + `cancel-in-progress: false` |
| Timeouts | `grep -c timeout-minutes <each of 7 workflows>` | ≥ job count per file |
| fmt clean | `terraform fmt -check -recursive services/` | exit 0 |
| Key not logged | `grep -n 'actual_api_key' apps/docker/onchain-stream-txs/src/4_mined_txs_crawler.py` | no log statement interpolates the raw value; unit test green |
| Doctor clean | `DADAIA_CONTEXT=dd-chain-explorer dadaia specs doctor` | 0 ERROR |
| Bugs closed | `grep -l 'status: Open' specs/bugs/` | empty (all Closed with `fixed_in:`) |
| Gate live (hml) | `gh api repos/:owner/:repo/environments` | `hml` has required_reviewers |
