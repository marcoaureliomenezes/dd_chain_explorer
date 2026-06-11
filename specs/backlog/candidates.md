# Backlog — Candidates for Future Releases

> Formal candidates: scoped, sourced, and ready for operator prioritization.
> Each item has been identified through the multi-specialist audit (2026-05-22) and PM mediation.
> Items blocked by operator decisions are marked `BLOCKED-BY-OPERATOR-DECISION: OQ-N`.

---

## Open Questions for Operator

All open questions from the tri-specialist audit have been resolved in the grill session on 2026-05-22.
See the Resolved section at the bottom of this file for the full decision record.

---

## LOW-Severity Issues (not scheduled in releases R1–R4)

These issues were identified in the audit but have low severity and low urgency.
They may be addressed in future maintenance releases or as part of a larger refactor.

### LOW-1 — API Health Alert: 50% pre-warning threshold (RESOLVED — see OQ-7)

**Summary:** Add per-key pre-warning alert at 50% error rate with 1h cadence.
**Source:** [DA] OQ-DA-03; OQ-7
**Resolution (grill 2026-05-22):** Scheduled as T-R4-NEW-2 in analytics-enrichment-r4.
Existing 80%/24h alert kept; new 50%/1h pre-warn alert added.

### LOW-2 — contracts_ingestion Lambda dead code candidate (RESOLVED — see OQ-5)

**Summary:** OQ-5 resolved in favour of Lambda Architecture (UNION path). The `contracts_ingestion`
Lambda remains active and is required by T-R3-04 (Silver intermediary `s_apps.transactions_from_lambda`).
**Source:** [DE] DE-L-003; ISSUE-031; OQ-5
**Resolution (grill 2026-05-22):** Lambda Architecture kept (Path A). Lambda is not dead code.

### LOW-3 — Dashboard API health alert threshold visualization

**Summary:** `03_gas_analytics.lvdash.json` and `04_api_health.lvdash.json` do not
display current alert threshold as a reference line. Makes threshold changes invisible to viewers.
**Source:** [DA] DA-015 (implicit)
**Suggested resolution:** Add reference line widget showing 80% threshold. Low effort (S).
Could be included in R4 A-series work with no new release.

### LOW-4 — ECS task definition CPU/memory right-sizing

**Summary:** ECS task definitions for Jobs 1–3 may be over-provisioned (observed low CPU
utilization). Right-sizing would reduce ECS cost further after FARGATE_SPOT migration.
**Source:** [SA] cost table §4.4 (implicit)
**Suggested resolution:** Profile CPU/memory usage for 7 days post R2 FARGATE_SPOT migration;
then right-size as a Terraform-only change. Low risk.

---

## Items Requiring Further Investigation

### INV-1 — PRD environment deploy sequence validation

**Summary:** PRD has never been deployed (HML is also unvalidated). Before PRD launch,
a complete HML deploy → validate → destroy cycle should be executed to confirm the full
Terraform module order and Databricks workspace provisioning.
**Source:** Architecture review; DEV-only validation so far
**Suggested resolution:** Operator-triggered HML validation run as a pre-PRD gate.

### INV-2 — REST API implementation scope and authentication model

**Summary:** US-P005 (REST API public endpoint) is the only user story not implemented.
No release currently scheduled for REST API.
**Source:** `specs/SPEC.md` US-P005; `specs/memory/product.md`
**Suggested resolution:** Separate planning session with operator. Requires new release
`rest-api-r5` with full SPEC/PLAN/TASKS. Auth model (OAuth2? API key?) must be decided.

### INV-3 — DynamoDB table TTL audit for BLOCK_CACHE entities

**Summary:** BLOCK_CACHE entities have TTL=1h. If a reorg occurs > 1h after block capture,
the cache misses and orphan detection may fail silently. This was not flagged in the audit
but is implied by the architecture.
**Source:** `specs/memory/architecture.md` DLT section; ADR-006
**Suggested resolution:** dadaia-grill-me session to verify reorg detection window is
sufficient; extend TTL to 6h if needed.

---

## Memory gaps from legacy-domains archive (T-R6-S4, 2026-06-10)

Content found in the archived `specs/domains/**` + `specs/releases/legacy/SPEC.md`
(now `specs/_archive/legacy-domains/2026-06-10/` + `specs/_archive/releases/legacy/`)
that is NOT yet represented in `specs/memory/` atoms. Target: v0.3.0 CLOSURE memory
pass (T-R6-S5/S6 window) or a follow-up release.

### GAP-LD-1 — No devops/CI-CD memory atom

**Summary:** GitFlow branch policy, the 7-workflow inventory + purposes, the `scripts/ci/`
script table, the version/tag scheme (`v{VER}`, `-dabs`, `-lambda`, `-infra`, `-lib`),
the HML-ephemeral/`if: always()` teardown law, and FR-DO rules existed only in
`devops/SPEC.md` — no memory atom covers CI/CD. v0.3.0 (WS-A/B3) rewrites much of this
flow, so the atom should be authored at CLOSURE from post-v0.3.0 reality, not from the
archived snapshot.
**Source:** `specs/_archive/legacy-domains/2026-06-10/devops/SPEC.md`
**Suggested resolution:** New `specs/memory/product/ci-cd.md` atom (or architecture.md
section) written by product-engineer in the v0.3.0 CLOSURE phase.

### GAP-LD-2 — Product latency NFR targets not in memory

**Summary:** NFR-P001 (Ethereum → S3 Bronze < 2 min), NFR-P002 (S3 → Gold < 5 min) from
the legacy product spec are stated nowhere in `specs/memory/`.
**Source:** `specs/_archive/releases/legacy/SPEC.md` §Requisitos Não-Funcionais
**Suggested resolution:** Add latency budget lines to `specs/memory/product/index.md`
(or capture-layer/medallion atoms) at CLOSURE — after verifying they still hold.

### GAP-LD-3 — Behavioral invariants of streaming jobs possibly under-documented

**Summary:** FR-level invariants from `applications/SPEC.md` — gap recovery (FR-APP-002),
4-stage calldata decode order (FR-APP-006), DynamoDB SEMAPHORE TTL-60s key exclusivity
(FR-APP-005), deadlock-never-drops-tx-hash (NFR-APP-004) — verify presence in
`specs/memory/product/capture-layer.md`; add any missing ones at CLOSURE.
**Source:** `specs/_archive/legacy-domains/2026-06-10/applications/SPEC.md`
**Suggested resolution:** Verification + delta edit of capture-layer atom in CLOSURE window.

### GAP-LD-4 — Alerts inventory partial in memory

**Summary:** `alert_api_keys` (80%/24h + 50%/1h pre-warn) and `alert_dynamodb_deadlock`
(P1) were documented in `data-analytics/SPEC.md`; data-catalog atom mentions only
"1 alert". Verify and complete the alerts inventory in serving-layer/data-catalog atoms.
**Source:** `specs/_archive/legacy-domains/2026-06-10/data-analytics/SPEC.md`
**Suggested resolution:** Verification + delta edit at CLOSURE.

### GAP-LD-5 — Engineering scaffold/code standards not in memory

**Summary:** `beteugeuse dlt/job create` scaffold rule (FR-DE-013) and the
`spark_python_task` code template (argparse, no `dbutils`, no `print()`, no catalog
hardcode) existed only in `data-engineering/SPEC.md`. If beteugeuse is still the
mandated scaffold tool, this belongs in `specs/memory/quality-assurance.md` or
tech-stack.md.
**Source:** `specs/_archive/legacy-domains/2026-06-10/data-engineering/SPEC.md`
**Suggested resolution:** Confirm tooling still current with operator; add to
quality-assurance.md at CLOSURE if so.

### GAP-LD-6 — INV-2 (REST API) design input now lives in the archive

**Summary:** The only written design for the unimplemented REST API (discovery interview
answers, endpoint specs, US-001..) is the archived spec-first trio. INV-2 above should
use `specs/_archive/legacy-domains/2026-06-10/applications/rest-api/{SPEC,PLAN,TASKS}.md`
as its design input when a rest-api release is planned. (INV-2's old reference
`specs/SPEC.md` US-P005 is now `specs/_archive/releases/legacy/SPEC.md`.)
**Source:** archive move T-R6-S4
**Suggested resolution:** No memory write needed — pointer note only.

---

## Hotfixes Pendentes

<!-- No hotfixes identified at time of this audit. -->
<!-- Any bug found post-R1 deployment should be filed here with severity and source evidence
     before being promoted to a hotfix release v1.0.x. -->

---

## Resolved Open Questions (grill session 2026-05-22)

All 7 original OQs + 1 surfaced during session were resolved by the operator on 2026-05-22.
Full decision record: `.dadaia/reports/dd-chain-explorer/product-engineer/2026-05-22T130225Z-refine-specs.html`

| OQ | Summary | Decision |
|----|---------|----------|
| OQ-1 | PRD catalog name | `prd` is canonical; specs memory update deferred to R1 CLOSURE |
| OQ-2 | DEV vs HML first restart | DEV-first confirmed |
| OQ-3 | Lakeview parameterization | DEV-only now; deferred to R4/post-INV-1 |
| OQ-4 | Orphaned Gold MVs | Drop from DLT (T-R3-NEW-1) |
| OQ-5 | transactions_lambda UNION intent | Keep Lambda Architecture; implement UNION in T-R3-04 (R3) |
| OQ-NEW-1 | KMS costs + encryption posture | Public-Default policy adopted; audit task T-R2-NEW-1 in R2 |
| OQ-6 | ECS FARGATE_SPOT scope | Jobs 1,2,3=SPOT; Jobs 4,5=On-Demand (T-R2-05) |
| OQ-7 | API keys alert threshold | Add 50%/1h pre-warn (T-R4-NEW-2); keep 80%/24h critical |
