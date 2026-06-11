---
name: bp-01-streaming-jobs-logger-inconsistency
status: Closed
severity: MEDIUM
reported: 2026-06-08
surface: apps/docker/onchain-stream-txs/src/*.py (best-practices — logger wiring)
session_id: null
fixed_in: c789e9c
closed: 2026-06-11
audit_ref: discovered during PM remediation grill (not in audit.md — operator add-on security/best-practices pass)
---

**Symptom:** The streaming job classes accept a `logger` in `__init__` and store
`self.logger`, but their processing methods reference a **module-global**
`LOGGER` instead. In `1_mined_blocks_watcher.py`, `MinedBlocksWatcher.run()`
calls `LOGGER.info(...)` at line 60 while `extract_stream()` uses
`self.logger.warning(...)`. `LOGGER` is only defined later inside the
`if __name__ == "__main__"` block (line 77: `LOGGER = logging.getLogger(...)`),
so the class method works only by closing over a module global that is
populated at import-of-main time. The dual logger path (`self.logger` vs global
`LOGGER`) is fragile: importing the class without running `main()` and calling
`run()` raises `NameError`, and the injected logger is silently ignored.

**Repro:**
```
grep -nE '\bLOGGER\b|self\.logger' apps/docker/onchain-stream-txs/src/1_mined_blocks_watcher.py
# class method line 60 uses LOGGER; constructor stores self.logger (unused in run)
# LOGGER defined only at module-main scope (line 77)
```

**Expected:** A job class should log through its injected `self.logger`
consistently; module-global `LOGGER` should not be referenced from inside class
methods. This makes the jobs testable in isolation (directly tied to DRIFT-01:
you cannot unit-test `run()` today without triggering the global).

**Notes:** This is the load-bearing reason the test gap (DRIFT-01) is hard to
close — the global-logger coupling blocks isolated instantiation. Fix this in
the same workstream as the tests. Scope the security/best-practices pass to
confirm there are no other latent global/closure references, no bare excepts (none
found in a first scan), and that secret material (Etherscan keys, SSM names) is
sourced from ParameterStore/env only (job 5 uses ParameterStoreClient — confirm).

**Closure evidence (2026-06-11, T-R6-S3):** re-verified on disk — all 5 job classes log
via `self.logger` inside methods (e.g. `1_mined_blocks_watcher.py:46,60`); module-global
`LOGGER` is confined to `if __name__ == '__main__'` blocks (jobs 1–2) and absent from
jobs 3–5 entirely. Fixed in commit `c789e9c`.
