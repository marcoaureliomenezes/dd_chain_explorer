# Consolidated Full-Platform Audit — dd-chain-explorer

> **Date:** 2026-06-11 (UTC stamp 20260611T001412Z)
> **Branch audited:** `feature/specs-first-docs-cleanup` @ 34686a7
> **Coordinator:** project-manager session (operator-requested full review + audit)
> **Evidence reports (this directory):**
> - `architecture-review.md` — software-architect (AWS + Databricks architecture, env parity, terraform design)
> - `security-review.md` — security-reviewer (IaC, CI credentials, secret scan, app code)
> - `cicd-terraform-review.md` — code-reviewer (GitHub Actions, terraform code quality, Makefile)
> - `sdd-drift-audit.md` — project-auditor (specs/memory vs code, SDD pattern compliance, scorecard)
>
> Context: the repo was largely produced by weaker models; the operator requested a
> zero-trust re-examination of every architectural, security, and infrastructure decision,
> plus full adoption of the current dadaia-workspace SDD pattern.

---

## 1. Verdict

**NOT production-trustworthy in its current state.** The platform *runs*, but its
control planes (Terraform, CI, Makefile) disagree with each other, the HML gate does
not validate what PRD executes, production applies are effectively un-reviewed, and
the documented architecture (memory) misrepresents the implemented one.

| Source | CRITICAL | HIGH | MEDIUM | LOW |
|---|---|---|---|---|
| Architecture review | 2 | 6 | 10 | 8 |
| CI/CD + Terraform review | 3 | 8 | 11 | 7 |
| Security review | 0 | 2 | 5 | 5 (+3 INFO) |
| SDD drift audit | — | 1 unique (2 cross-refs) | 2 | — |
| **Total (deduplicated)** | **5** | **17** | **28** | **20** |

**SDD compliance scorecard (project-auditor):** Architecture 6 · Product 6 ·
Tech-stack 8 · Security 4 · Tests 5 · Agent-surface 6 → **5.8/10** (moderate-drift
band). `dadaia specs doctor`: **[fail] 8 ERROR / 18 WARN.**

---

## 2. The five CRITICALs

| ID | Finding | Evidence |
|---|---|---|
| ARCH-C1 | **Split-brain PRD Databricks control plane.** Stale monolith `services/prd/05_databricks/` (state key `prd/databricks`) declares the same account-level resources as the newer `05a_databricks_account` + `05b_databricks_workspace` pair. Makefile + `tf_validate_all.sh` still drive the stale stack while CI drives the new pair. `prevent_destroy` exists only in the dead copy. | architecture-review.md §1 C1 |
| ARCH-C2 | **HML gate does not test what PRD runs.** `dlt_ethereum` HML target reads `hml-raw` while Firehose writes `hml-lakehouse/raw/` (all 14 other bundles + CI use lakehouse); HML DABs deploy to a hardcoded shared dev workspace, not the MWS workspace Terraform provisions. | architecture-review.md §1 C2 |
| CI-C1 | **Blind auto-approved production applies.** PRD/HML `terraform apply` for ALL stacks runs under a single environment gate with no plan visible to the approver (`deploy_cloud_infra.yml:181-273`, `deploy_env.sh:79`). | cicd-terraform-review.md C1 |
| CI-C2 | **Apply decisions cross-contaminate between stacks.** `deploy_env.sh:77` infers apply/skip by `grep` + `tail -1` over the shared append-only `$GITHUB_OUTPUT`; the `/dev/null` fallback silently skips applies that have changes. | cicd-terraform-review.md C2 |
| CI-C3 | **Nuclear destroy-all has no concurrency group.** `destroy_all_cloud_infra.yml` (destroys the state bucket + lock table) can race with itself → corrupted/destroyed shared state. | cicd-terraform-review.md C3 |

---

## 3. Cross-cutting themes (what the weak models actually did wrong)

1. **Copy-paste instead of parameterization.** dev/hml/prd are three diverging code
   trees of the same stacks (HML↔PRD same-stack *structural* file drift — CI-H7); PRD
   hand-rolls vpc/iam/ecs inline while HML uses `services/modules/` (ARCH-H1); 10
   near-identical plan jobs (CI-H6); 15 DABs bundles with duplicated, already-diverged
   config (ARCH-M3). **One fix dissolves a third of all findings: single stack
   definition + per-env tfvars, and module reuse everywhere.**
2. **Abandoned layers were never deleted.** Stale `05_databricks` monolith (C1), stale
   Makefile control plane with broken targets (ARCH-H2, CI-L1/L2/L5), Kafka-era argv
   wired into live ECS task definitions (ARCH-H5), vestigial ABI cache + dead IAM
   grants (ARCH-M6), phantom REST API spec with zero implementation (ARCH-M8). The
   capture layer as a whole is superseded by the sibling `dd-chain-capture` repo with
   **no deprecation ADR**.
3. **Error masking everywhere.** `tail -1` apply flags (CI-C2), `tee` masking plan exit
   codes before unconditional apply (CI-H8), pervasive `|| true` (CI-M1), `tail -N`
   truncating plans (CI-M2). The pipelines are built to look green.
4. **Reproducibility ignored.** `.terraform.lock.hcl` gitignored (ARCH-H6), three
   different terraform version floors in one repo (CI-H2), modules without
   `required_providers` (CI-M7), `MUTABLE` ECR tags (SEC-L02).
5. **Identity/secrets debt.** Static long-lived AWS keys in all 7 workflows including
   PR-triggered plans (SEC-H-02 + SEC-M-05); raw Infura key logged in cleartext and
   propagated CloudWatch→Firehose→S3→Databricks (SEC-H-01); Databricks bootstrap token
   in TF state (SEC-M-03); Kinesis/SQS unencrypted (SEC-M-01/M-02, ARCH-M9).
6. **Docs/memory describe an imagined system.** `specs/memory/architecture.md`
   REJECTED on the architecture-fidelity gate (ARCH-H3); ADR-005 Lambda-architecture
   union documented but never implemented — `contracts_ingestion` is a dangling
   producer (DRIFT-1); prod catalog name drift (ARCH-M4); HML "100% ephemeral" claim
   contradicted by code (ARCH-M2); 7 of 8 `specs/bugs/` already fixed but still Open.

## 4. Environment-parity summary

Full matrix in `architecture-review.md`. Headline: **dev** is compose/local + 2 light
stacks with remote S3 state despite SPEC saying local (ARCH-M1); **hml** lacks
tf_state/account/lambda stacks, uses shared modules, deploys DABs to the wrong
workspace (C2); **prd** is the full 9-stack set but hand-rolled inline (H1) and
carries the split-brain Databricks layer (C1). Differences are mostly **accidental
drift/abandonment, not recorded cost decisions** (single-AZ public subnet +
FARGATE_SPOT + 1 Kinesis shard have no ADR — ARCH-H4).

## 5. Remediation sequencing (proposed)

Tracked as backlog epic `specs/backlog/platform-audit-remediation-20260611.md`
(CANDIDATE — operator picks via PM → product-engineer release definition + grill).

1. **Stop-the-bleeding (CI safety):** CI-C1/C2/C3 + CI-H8 — plan-visible gated
   applies, per-stack output files, concurrency groups, kill error masking.
2. **Secrets/identity:** SEC-H-01 key-logging purge (+ scrub shipped logs), SEC-H-02
   OIDC migration, SEC-M-05 PR-plan credential isolation.
3. **Kill the split brains:** ARCH-C1 stale Databricks stack removal (state surgery),
   ARCH-C2 HML target fix, ARCH-H2 Makefile retirement/reduction.
4. **Parameterize:** one stack tree + per-env tfvars; PRD onto shared modules; DABs
   config dedup; lock files committed; unified version floors.
5. **Deprecation ADR for the capture layer** (dd-chain-capture supersession) + dead
   code/dead infra removal wave.
6. **SDD/memory fidelity:** rewrite architecture.md + data-catalog.md to reality,
   close fixed bugs, fix doctor errors (8× missing `session_id`), retire
   `specs/domains/` legacy tree, wire the 71 streaming-job tests into CI.

## 6. Workspace-tooling notes (separate from this repo)

- `dadaia reports validate` rejects handoffs whose `artifact.path` points at
  `specs/audits/` — already filed as
  `repos/dadaia-workspace/specs/bugs/handoff-artifact-path-cannot-reference-specs-audits.md`.
- Working-tree hygiene at audit time: `.hypothesis/` at repo root (removed by
  coordinator post-audit), `apps/dabs/**/.databricks/` bundle state dirs and stray
  `.terraform/` dirs on disk (untracked; gitignore + cleanup tracked in backlog WS-G).
