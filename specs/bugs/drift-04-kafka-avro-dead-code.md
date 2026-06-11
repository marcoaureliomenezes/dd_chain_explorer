---
name: drift-04-kafka-avro-dead-code
status: Closed
fixed_in: cb218f7 + rmdir T-R6-S2 (20260611)
severity: LOW
reported: 2026-06-08
surface: apps/docker/onchain-stream-txs/src/{configs,schemas} (dead Kafka/Avro artifacts)
session_id: null
audit_ref: specs/audits/20260609T013037Z/audit.md#DRIFT-04
---

**Symptom:** 7 Avro schema files (`src/schemas/*.json`) and 3 Kafka config
files (`src/configs/topics.ini`, `consumers.ini`, `producers.ini`) remain in a
live source dir. ADR-001 explicitly removed Kafka / Schema Registry ("no
Avro/Protobuf; Kinesis + Firehose Direct Put"). Live code comments confirm the
migration (`# replaces Kafka Avro consumer/producer`). No active module imports
these files.

**Repro:**
```
ls apps/docker/onchain-stream-txs/src/schemas/   # 7 *_avro.json + dlq + decoded
ls apps/docker/onchain-stream-txs/src/configs/   # topics.ini consumers.ini producers.ini
grep -rn "topics.ini\|_avro" apps/docker/onchain-stream-txs/src/*.py  # no importer
```

**Expected:** Dead code that contradicts the approved architecture (ADR-001)
should not persist in a live source tree.

**Notes:** `topics.ini:2` comment: "Usado por 0_topics_creator.py para criar os
tópicos no Kafka" — `0_topics_creator.py` no longer exists. Safe to delete;
verify no importer before removal. Low urgency, non-blocking.

**Verification note (2026-06-11, T-R6-S3):** substantive fix re-verified — all 7 Avro
schemas and 3 Kafka config files are gone (`configs/` and `schemas/` contain zero
files), but both empty directories still exist on disk. Closure is blocked on
T-R6-S2 (`rmdir`) executed 2026-06-11 — both empty dirs removed; bug Closed.
