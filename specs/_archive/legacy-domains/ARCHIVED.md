# ARCHIVED — legacy domains specs

> **Archived:** 2026-06-10
> **By:** product-engineer (task T-R6-S4, release v0.3.0 — deferred T-R5-F1)
> **Reason:** canon migration — pre-release-model "domain" specs superseded by the
> release-based SDD model + atomic memory (dadaia-workspace canon).

## What moved here

`specs/domains/` (8 files, pattern-v0 domain specs, all `**Status:** Implementado` —
a non-canonical status token):

| Path (under `2026-06-10/`) | Content |
|---|---|
| `applications/SPEC.md` | Streaming jobs, Lambdas, dm-chain-utils domain spec |
| `applications/rest-api/{SPEC,PLAN,TASKS}.md` | REST API spec-first feature — **never implemented** |
| `data-engineering/SPEC.md` | DLT pipelines, batch jobs, Medallion domain spec |
| `data-analytics/SPEC.md` | Dashboards, Genie, alerts domain spec |
| `infrastructure/SPEC.md` | Terraform/AWS environments domain spec |
| `devops/SPEC.md` | CI/CD, GitFlow, versioning domain spec |

Separately, `specs/releases/legacy/SPEC.md` (pre-release-model product spec, US-P001..005)
moved to `specs/_archive/releases/legacy/`.

## Where current truth lives

These files are **historical snapshots** (state ~2026-04/05) and are NOT sources of
truth. The current product is described atomically in:

- `specs/memory/product/index.md` + `specs/memory/product/<slug>.md` (capture-layer,
  medallion-pipelines, serving-layer, aws-resources, data-catalog)
- `specs/memory/architecture.md`, `specs/memory/tech-stack.md`,
  `specs/memory/quality-assurance.md`
- `specs/constitution.md`

Known content not yet represented in memory at archive time (devops/CI-CD atom, product
latency NFRs, selected behavioral invariants) is tracked in `specs/backlog/candidates.md`
(entries dated 2026-06-10) for the v0.3.0 CLOSURE memory pass (T-R6-S5/S6 window).

## Do not edit

`specs/_archive/**` is FROZEN (read-only). Re-opening any of this content requires a new
release that supersedes it.
