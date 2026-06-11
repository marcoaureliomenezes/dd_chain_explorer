---
name: drift-01-streaming-jobs-zero-tests
status: Closed
severity: HIGH
reported: 2026-06-08
surface: apps/docker/onchain-stream-txs/src (5 streaming job entry points)
session_id: null
fixed_in: 226740e
closed: 2026-06-11
audit_ref: specs/audits/20260609T013037Z/audit.md#DRIFT-01
---

**Symptom:** The 5 production capture-layer streaming jobs
(`1_mined_blocks_watcher.py`, `2_orphan_blocks_watcher.py`,
`3_block_data_crawler.py`, `4_mined_txs_crawler.py`, `5_txs_input_decoder.py`)
have ZERO unit or integration tests. Only the shared utility library
(`utils/tests/unit/`) is tested. The single test under the app
(`apps/docker/onchain-stream-txs/test/test_server.py`, 18 lines) is a TCP
server smoke test and covers none of the job processing logic.

**Repro:**
```
find apps/docker/onchain-stream-txs -name "*test*"   # only test/test_server.py
ls apps/docker/onchain-stream-txs/src/               # 5 job modules, no tests
```

**Expected:** Memory atoms `specs/memory/quality-assurance.md` and
`specs/memory/product/capture-layer.md` describe these 5 jobs as
production-critical; the SDD quality contract implies the production capture
surface is covered by behavioral tests. Each job's main processing loop should
have at least contract-level unit tests.

**Notes:** Single largest quality risk in the repo (Tests dimension scored
4/10). Decoder job 5 (17 KB, multi-key Etherscan + DynamoDB ABI cache + 4byte
fallback) is the highest-value target. Remediation: qa-engineer defines the
test plan, software-engineer implements.

**Closure evidence (2026-06-11, T-R6-S3):** re-verified on disk — 71 `def test_`
across 6 files in `apps/docker/onchain-stream-txs/tests/unit/` covering all 5 jobs +
etherscan multi-key. Fixed in commit `226740e`. (CI wiring of these tests is tracked
separately — audit DRIFT-N08.)
