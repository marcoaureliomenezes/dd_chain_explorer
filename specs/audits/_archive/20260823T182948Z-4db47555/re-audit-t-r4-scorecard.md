# T-R.4 — Ship-gate re-score (live)

> **Audit:** `20260823T182948Z-4db47555` — gate lane, same audit, no new audit directory.
> **Produced:** 2026-08-23T22:17:21Z · **Auditor:** `project-auditor` · **Context:** `dd-chain-explorer` · **Release:** `v0.5.0`
> **Rubric:** identical to the consolidated audit — `dd-audit-project`, six dimensions A–F,
> `weighted = A·0.20 + B·0.25 + C·0.15 + D·0.20 + E·0.15 + F·0.05`, `final = min(weighted, floor + 2)`.
> **Prior:** 6.1 live / 7.4 projected (baseline 3.6).
> **Ship gate (`SPEC.md` §4):** overall ≥ 7 **and** no dimension < 5.

---

## 1. Verdict

**Overall 7.6 / 10 · floor 7 · gate PASS.**

Both gate conditions hold: 7.6 ≥ 7, and the lowest dimension is 7 (≥ 5). The live score now
**exceeds** the audit's own projection of 7.4, because two things the projection could only
assume were verified running: the OIDC deploy roles exist in the account, and the CI quality
gate (including the test suite) actually executed and passed — twice, on two independent PRs.

Every claim below was verified on the executed path this session. Nothing is taken on report.

---

## 2. Compliance scorecard

| Dim | Dimension | Prior live | **Now** | Δ | One-line justification (live evidence verified this session) |
|---|---|---|---|---|---|
| A | Architecture | 6 | **8** | +2 | Deployed estate now matches the repo: `aws ec2 describe-vpcs` → **zero** non-default VPCs in `us-east-1`/`us-east-2` (legacy shell gone); `aws iam list-roles` → **zero** `firehose\|kinesis\|onchain` roles (capture-era IAM destroyed, `prd/03_iam` clean); `aws ecs list-task-definition-families --status ACTIVE` → empty in `us-east-2`, only the AWS console sample `first-run-task-definition` in `us-east-1`; state bucket holds **8 keys, 7 of which are the live stacks** (was 8 keys for *destroyed* stacks). Deductions: the alien `capture/ecr/terraform.tfstate` key survives, and ADR-007 + the rewritten `architecture.md` are committed locally but **absent from `origin/main`**. |
| B | Product | 5 | **7** | +2 | RES-01 is dead: `gh pr checks 29` → **10/10 pass**, including all 9 `plan_on_pr` jobs and the `Preflight — OIDC role variable` — the flagship WS-A deliverable works end-to-end, and a **second** independent green run (`32668967364`, 3m49s) landed on the Dependabot actions PR. Databricks: 6 jobs, **100 % bundle-managed, 0 orphans** (was 11 orphans), every schedule `PAUSED`/absent (hourly ingestion no longer ENABLED), zero repo-owned lambdas left. Deduction: the catalogued `cicd-pipeline` feature is **still partly broken on the default branch** — `Dependabot Updates / pip in /apps/lambda` **failed twice at 21:54Z on `main`** (runs `32668924886`, `32668921912`), because the root-cause fix `018ec7d` is unpushed. |
| C | Tech stack | 8 | **8** | 0 | One version axis at `0.5.0`, hash-locked deps, `ruff`/`mypy` clean — and now *proven* by CI rather than asserted: `Quality gate (fmt / validate / actionlint / lint / tests)` **pass, 3m0s**. `gh api dependabot/alerts?state=open` → **0**. Offsetting: `origin/main` still carries `release_origin: v0.4.0` in `tech-stack.md` and the dependabot-unparseable `requirements*.lock` names; both fixes exist only on unpushed local `develop`. Net zero. |
| D | Security | 6 | **7** | +1 | Least privilege is no longer unprovable — the four OIDC roles **exist live** (`dm-chain-explorer-gha-deploy-{dev,hml,prd}`, `dm-chain-explorer-gha-readonly-plan`), and the readonly role carries a read-only action set plus an explicit inline `dm-gha-self-mutation-deny` (bootstrap rev5, read-gap closed). Branch protection verified by API: `main` = **9 required checks + strict**, no force-push, no deletion; `develop` = no force-push, no deletion. GitGuardian pass, `scorecard.yml` active, 0 open alerts, zero dead privileged capture-era roles. Deductions: **pip CVE surveillance is dead on `main`** (the failing Dependabot pip job above), the Databricks estate still runs under the operator identity while `dm_spn_user` sits unused, 7 LOW residuals routed to intake, and the first drift cron has not fired. |
| E | Tests | 6 | **8** | +2 | The single largest live deduction is closed: a suite **is** executed by CI now — the quality gate ran green on PR #29 and again on the Dependabot PR, against a repo whose last workflow run of any kind had been 2026-04-11. 143/143 green, no skips, no quarantine, no tombstones; the `T-D.2` ordering inversion is resolved and recorded under `## Test dispositions` in `CLOSURE.md`. Deduction: `drift_detection` is `active` on the new default branch `main` but its first scheduled run has not yet fired, so the detection lane is armed-but-unproven. |
| F | Design / serving | 6 | **8** | +2 | `T-C.7` is live: `databricks credentials list-credentials` → `dm-hml-s3-credential`, and `databricks external-locations list` → `dm-hml-lakehouse` + `dm-hml-raw-data`, both backed by real buckets — the `hml` dashboards finally have resolvable data. Stale `.bundle` roots and the orphan dashboard are gone (0 orphan jobs, 6/6 bundle-deployed). Deduction: the non-canon `de-lakehouse-credential` survives in Unity Catalog, and `serving-layer.md` is published only locally. |

### Aggregation

| | A | B | C | D | E | F | weighted | floor | **final** |
|---|---|---|---|---|---|---|---|---|---|
| Prior — live | 6 | 5 | 8 | 6 | 6 | 6 | 6.05 | 5 | 6.1 |
| Prior — projected | 8 | 6 | 8 | 8 | 7 | 8 | 7.35 | 6 | 7.4 |
| **T-R.4 — live** | **8** | **7** | **8** | **7** | **8** | **8** | **7.55** | **7** | **7.6 / 10** |

`weighted = 8(0.20) + 7(0.25) + 8(0.15) + 7(0.20) + 8(0.15) + 8(0.05) = 7.55`;
`floor + 2 = 9`; `final = min(7.55, 9) = 7.6`.

**Gate arithmetic:** 7.6 ≥ 7 ✅ · min dimension 7 ≥ 5 ✅ → **PASS**. Delta vs baseline 3.6: **+4.0**.

---

## 3. Claim verification log

| # | Operator claim | Verdict | Evidence |
|---|---|---|---|
| 1 | v0.5.0 shipped, PR #29 merged, tag `v0.5.0` | **CONFIRMED** | `gh pr view 29` → `MERGED`, `mergedAt 2026-08-23T21:53:55Z`, mergeCommit `9ad2165`, `develop` → `main`. `git log origin/main -1` → `9ad2165`. `git tag -l` → `v0.5.0`. |
| 2 | CI alive end-to-end, all `plan_on_pr` checks green, bootstrap rev5 applied | **CONFIRMED** | `gh pr checks 29` → 10/10 pass. Four `gha-*` roles exist in account `016098071081`; readonly role policy set is read-only + `dm-gha-self-mutation-deny`. |
| 3 | Branch protections on `main` and `develop` | **CONFIRMED** | `main`: 9 contexts, `strict: true`, force-push/deletion false. `develop`: force-push/deletion false. Default branch = `main`. |
| 4 | drift/scorecard/dependabot live, pip parse error fixed, 0 open alerts | **PARTIAL** | Workflows `Drift Detection`, `Scorecard supply-chain security`, `Dependabot Updates` all `active`; 0 open alerts; actions-ecosystem Dependabot PR opened and went green. **But the pip fix `018ec7d` is unpushed** — `git merge-base --is-ancestor 018ec7d origin/main` → NO — and the pip job **failed twice on `main` at 21:54Z**. |
| 5 | Live cutover executed | **CONFIRMED** | Zero non-default VPCs; zero capture-era roles; zero repo log groups (only Databricks CFN + console sample); **zero EventBridge rules** in either region (schedule not merely disabled — absent); 0 orphan Databricks jobs, 6/6 bundle-managed; state bucket down to the 7 live stack keys. |
| 6 | CLOSURE.md Aprovado, dispositions complete, memory rewritten, −3,708 net | **CONFIRMED (locally)** | `CLOSURE.md` line 3 `**Status:** Aprovado`; sections `## Dispositions` → `Audit 20260823T145726Z-4db47555 — DRIFT-01..31 (31/31)` and `Audit 20260611T001412Z-cb56f84c — 82 lane ids (82/82)`; `## Size accounting`; `## Memory updates`; `## Test dispositions`; `## Intake candidates` incl. `### Pre-approved intake`. Local `tech-stack.md` → `release_origin: v0.5.0`. |
| 7 | Known open items scored honestly | **CONFIRMED** | Scored as deductions in B (prd/06_lambda absent — 0 lambdas live), D (7 LOW residuals, unfired cron), E (unfired cron), A/C/F (publication gap). |

---

## 4. Findings that survive the gate

| ID | Dim | Sev | Finding | Evidence | Owner |
|---|---|---|---|---|---|
| GATE-01 | B / C / D | **MEDIUM** | The entire CLOSURE — `CLOSURE.md`, ADR-007, 8 rewritten memory atoms, and the Dependabot pip fix `018ec7d` — is **committed only to unpushed local `develop`**. `origin/main` still reads `phase: IMPLEMENTATION`, `release_origin: v0.4.0`, no `CLOSURE.md`, no ADR-007, and the `.lock` filenames that break Dependabot pip. | `git rev-parse origin/develop` → `36a6cee` vs local `develop` → `5bc8177`; `git cat-file -e origin/main:specs/releases/v0.5.0/CLOSURE.md` → ABSENT; Dependabot pip runs `32668924886`/`32668921912` **failure** on `main`. | `software-engineer` (push `develop`, then PR to `main`) |
| GATE-02 | E | **INFO** | `dadaia specs doctor` → 1 error, `SPEC-DOC-024`: `ACTIVE.md phase='CLOSURE'` with 2 unfinished task markers. Self-referential — the two markers are `T-R.4` (this gate, `[-]`) and `T-E.8` (archive, `[ ]`). Clears itself when this scorecard lands and the audit archives. | `specs/releases/ACTIVE.md`, `TASKS.md` | `product-engineer` |
| GATE-03 | A | **LOW** | `capture/ecr/terraform.tfstate` survives in the state bucket — a state object for a stack retired in v0.4.0. | `aws s3 ls s3://dm-chain-explorer-terraform-state/ --recursive` | intake candidate |
| GATE-04 | F | **LOW** | Non-canon Unity Catalog credential `de-lakehouse-credential` survives alongside the `dm-*` canon. | `databricks credentials list-credentials` | intake candidate |
| GATE-05 | D | **LOW** | Databricks jobs still carry the operator identity as creator while `dm_spn_user` remains unused; carried forward from the prior audit's live column. | `databricks jobs list` → `creator_user_name` = operator | intake candidate |
| GATE-06 | D / E | **INFO** | `drift_detection` is `active` on `main` but the first scheduled run has not fired — the lane is armed, not proven. | `gh api actions/workflows` → `Drift Detection: active`; `gh run list` shows no drift run | none (time) |

None of these breach the gate. GATE-01 is the only one with live consequence and it is one `git push` away.

---

## 5. Recommended actions

Ordered by severity. Per this agent's contract, each names the agent who acts — never "fix it yourself".

1. **`software-engineer`** — push local `develop` (`5bc8177`, carrying `018ec7d` + the CLOSURE commit), then open the `develop` → `main` PR so the default branch receives the CLOSURE, ADR-007, the post-release memory atoms and the `requirements*.txt` rename. Watch CI to green. This closes GATE-01 and stops the recurring Dependabot pip failure on `main`.
2. **`product-engineer`** — flip `T-R.4` to `[x]` on the strength of this scorecard, then execute `T-E.8` (archive this audit and `20260823T145726Z-4db47555` to `specs/audits/_archive/`, naming release `v0.5.0`), clearing `SPEC-DOC-024` and the three `SPEC-DOC-038` warnings.
3. **`project-manager`** — compile GATE-03, GATE-04 and GATE-05 into the operator intake report alongside the 7 security LOW residuals and the `T-B.14`/`T-B.7` pre-approved deferrals. Do not materialize backlog entries without operator ratification.
4. **`project-auditor`** (next cycle) — re-verify GATE-06 after the first `drift_detection` cron fires; a green scheduled drift scan is the last unproven detection lane.

---

## 6. Evidence sources

Direct executed-path verification only — no evidence agents were dispatched for this gate lane,
since every open question was answerable by a live API or repository probe within the budget.

- `gh pr view 29`, `gh pr checks 29`, `gh run list`, `gh api repos/:owner/:repo/{branches/{main,develop}/protection, actions/workflows, dependabot/alerts?state=open}`
- `git log origin/main`, `git tag -l`, `git merge-base --is-ancestor`, `git cat-file -e origin/main:…`, `git show origin/main:…`, `git show --stat 018ec7d`
- `aws sts get-caller-identity`, `aws iam list-roles`, `aws iam list-role-policies`, `aws iam get-role-policy`, `aws ec2 describe-vpcs`, `aws ecs list-task-definition-families`, `aws lambda list-functions`, `aws logs describe-log-groups`, `aws events list-rules`, `aws s3 ls`, `aws s3api list-buckets` (both `us-east-1` and `us-east-2`)
- `databricks jobs list`, `databricks external-locations list`, `databricks credentials list-credentials`
- `dadaia specs doctor`
- Prior audit rubric and scores: `specs/audits/20260823T182948Z-4db47555/consolidated-audit.md`
- Release artifacts: `specs/releases/v0.5.0/{CLOSURE.md,TASKS.md}`, `specs/releases/ACTIVE.md`
- Memory atoms read: `specs/memory/product/catalog.json`, `specs/memory/product/capture-layer.md`, `specs/memory/tech-stack.md`
