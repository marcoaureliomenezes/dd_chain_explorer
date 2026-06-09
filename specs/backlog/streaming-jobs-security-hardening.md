# Backlog — CANDIDATE: Streaming Jobs Security Hardening (F-04..F-09)

> **Status:** CANDIDATE — NOT picked into any release.
> **Owner:** project-manager (sole backlog author).
> **Created:** 2026-06-09
> **Operator decision:** backlog for later. Do NOT scope a hardening release now.
> **Source:** WS-E security + best-practices review of the 5 streaming job files,
> handoff `.dadaia/handoff/dd-chain-explorer/2026-06-09T040000Z-security-reviewer-ws-e-streaming-jobs.handoff.json`
> (report `.dadaia/reports/dd-chain-explorer/security-reviewer/2026-06-09T040000Z-security-ws-e-streaming-jobs.html`).
> Verdict: **APPROVED** (0 CRITICAL, 0 HIGH). F-01/F-02/F-03 (MEDIUM) are folded into the
> active remediation set (WS-E); the **deferred LOW/INFO** findings below are captured here
> as future-prioritization candidates.

These are hardening / observability improvements, not exploitable vulnerabilities under
the current AWS ECS perimeter. They were explicitly deferred by the reviewer to backlog.

---

## Deferred findings (LOW / INFO)

| Candidate | Finding | Sev | OWASP/CWE | File:line | Recommended fix |
|---|---|---|---|---|---|
| SEC-HARD-04 Magic constant | **F-04** hardcoded `txs_threshold=100` inside `run()` | LOW | A05 / CWE-1188 | `4_mined_txs_crawler.py:86` | Expose as constructor param or env var, default 100 documented |
| SEC-HARD-05 Silent 4byte swallow | **F-05** `except Exception: pass` hides 4byte.directory lookup failures. **Cross-ref: same issue as code-reviewer's S-01 (rc-1) — the bare except is now at `etherscan_multi.py:154` (`get_4byte_signature`) after edits; do not file S-01 separately.** | LOW | A09 / CWE-778 | `utils_decode/etherscan_multi.py:154` (was cited 148-149) | Log at DEBUG before returning None; narrow the bare `except Exception` to the expected request/parse exceptions; convert static→instance method for `self.logger` |
| SEC-HARD-06 Unbounded lru_cache | **F-06** `@lru_cache(maxsize=4096)` keyed on raw ABI JSON string → possible OOM | LOW | A04 / CWE-400 | `5_txs_input_decoder.py:255-260` | Key cache on `SHA-256(abi_json)`; document maxsize justification |
| SEC-HARD-07 API-key exhaustion silent loss | **F-07** all-keys-exhausted RuntimeError caught + logged, then execution continues with no valid key | LOW | A04 / CWE-754 | `4_mined_txs_crawler.py:49` | Re-raise / `SystemExit` so ECS health check restarts the container |
| SEC-HARD-08 Dockerfile root + unpinned base | **F-08** runs as root, no non-root `USER`, base image not digest-pinned | INFO | IaC | `apps/docker/onchain-stream-txs/Dockerfile:4` | Add `adduser` + `USER appuser`; pin base to SHA256 digest; set `no-new-privileges` in ECS task def |
| SEC-HARD-09 pip-audit not run | **F-09** CVE status of 10 deps unconfirmed (no local venv; static inspection only, no known-vulnerable floors as of Aug 2025) | INFO | A06 | `apps/docker/onchain-stream-txs/requirements.txt` | Add `pip-audit` to CI pre-push gate for this repo (see OI-1) |

---

## rc-1 reviewer findings (deferred to backlog — push precondition cleared)

> **Source:** rc-1 ship-gate reviewers (`audit-remediation-r5`). These 3 NEW minor findings
> were surfaced during the rc-1 review and explicitly deferred to backlog as a push
> precondition. All **CANDIDATE — NOT picked**.

| Candidate | Finding | Sev | OWASP/CWE | File:line | Recommended fix |
|---|---|---|---|---|---|
| SEC-HARD-10 Raw key tail in rate-limit log | **D-01** (code-reviewer) the `key[-4:]` fallback logs the last 4 chars of a raw API key in the rate-limit warning | LOW | A09 / CWE-532 | `utils_decode/etherscan_multi.py:115` | Replace the `key[-4:]` fallback with an `"UNKNOWN_KEY"` sentinel so no raw key material reaches logs |
| TEST-HARD-01 Missing fallback-log test | **T-01** (code-reviewer) no test covers the `key[-4:]` rate-limit fallback log path | LOW | — / test-coverage | `tests/unit/test_4_mined_txs_crawler.py` (new test) | Add a test asserting the rate-limit warning emits the `"UNKNOWN_KEY"` sentinel (pairs with SEC-HARD-10) when the key is absent from `_key_names` |
| TEST-HARD-02 Dead/no-op rotation test | **QA-LOW** (qa-engineer) `test_rate_limit_429_triggers_rotation` has a dead `with patch.dict(...): pass` block and only exercises the happy path; the rotation it claims to test is never asserted (exhaustion path is covered elsewhere) | LOW | — / test-fidelity | `tests/unit/test_4_mined_txs_crawler.py:121-148` | Remove the dead `patch.dict ... pass` block; make the test actually drive a 429 → `elect_new_api_key` → retry-with-new-key and assert the rotation occurred (returned key changes) |

---

## Related open items (reviewer `decisions_required`)

- **OI-1** — Add `pip-audit` to the CI pre-push gate for `apps/docker/onchain-stream-txs/`
  to confirm zero CVEs. (Pairs with SEC-HARD-09.)
- **OI-2** — `dm-chain-utils==0.2.9` was out of WS-E scope; schedule a separate security
  pass for it. (Candidate for its own backlog item if/when picked.)
- **OI-3** — Confirm whether the ECS task definition constrains `NETWORK` to known values;
  if yes, the active F-02 finding can be downgraded to LOW. (Investigation, not picked.)

---

## Notes for a future planning round

- **Grill is mandatory** before this reaches a SPEC. Open ambiguities: SEC-HARD-07
  fail-fast-vs-degrade behavior (does a container restart loop on persistent key
  exhaustion make things worse?) and SEC-HARD-09's pip-audit gate placement.
- **Not exploitable today** per the reviewer; priority is hygiene/observability. Bundling
  SEC-HARD-04/05/06/07 (code) separately from SEC-HARD-08/09 (Docker/CI) is reasonable.
- SEC-HARD-10 + TEST-HARD-01 are a tight code+test pair (raw-key-tail removal and its
  coverage) and should be scoped together. TEST-HARD-02 is independent test-fidelity hygiene.
- **S-01 is NOT a separate candidate** — it is the same bare-except as **F-05**
  (SEC-HARD-05); see that row's cross-reference note.
- Evidence pointers (handoff JSON + HTML report paths above) must be preserved when this
  is folded into a release SPEC.
