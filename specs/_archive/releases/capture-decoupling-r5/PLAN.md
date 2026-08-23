# PLAN: capture-decoupling-r5

**Status:** Aprovado
**Release:** capture-decoupling-r5
**Owner:** product-engineer
**Created:** 2026-05-23
**Source:** SPEC.md (this release) — ADR-CAPTURE-001 through ADR-CAPTURE-009

---

## Strategy

Five work-packages executed in dependency order. WP-0 contains hard blockers that cannot
be bypassed. WP-1 and WP-2 can run in parallel once WP-0 unblocks them. WP-3 depends on
WP-1 (library) and WP-2 (infrastructure running). WP-4 can be authored in parallel with
WP-1/WP-2 but deployment gates require WP-3 complete. WP-5 is the validation and cutover
phase — strictly sequential after WP-3 and WP-4 pass their gates.

```
WP-0: Pre-conditions (must resolve before any implementation)
  ├── pipeline-restart-r1 ARCHIVED  ──────┐
  └── dm-app-logs DLT Bronze fix          │ (parallel authoring, must land before DEV cutover)
                                          │
WP-1: Repository + library (dd-chain-capture) ──────┐
WP-2: Confluent Platform + Redis infra ─────────────┤
  └── both must complete before WP-3 starts          │
                                                      ▼
WP-3: Python capture job adaptation ─────────────────┤
WP-4: CI/CD + deployment (parallel with WP-1/2/3)   │
                                                      ▼
WP-5: Integration validation + cutover ──────────────┘
```

**Critical path:** WP-0 gate → WP-1 + WP-2 (parallel) → WP-3 → WP-5.

---

## WP-0 — Pre-conditions

**Owner:** product-engineer (gating), devops-engineer (execution), data-engineer (DLT fix)
**Gate:** Nothing in WP-1 through WP-5 may begin implementation until these are satisfied.

### WP-0.1 — pipeline-restart-r1 must reach ARCHIVED

`pipeline-restart-r1` has overlapping write surfaces with this release (ECS task
definitions, capture layer infrastructure). Concurrent implementation is not safe.

Gate passed when:
- All tasks in `pipeline-restart-r1/TASKS.md` marked `[x]`
- `specs/releases/pipeline-restart-r1/CLOSURE.md` written
- Release directory archived to `specs/_archive/releases/pipeline-restart-r1/`
- `specs/releases/ACTIVE.md` updated to `release: capture-decoupling-r5`

### WP-0.2 — dm-app-logs DLT Bronze fix (dd-chain-explorer)

Scope: `apps/dabs/dlt_app_logs/` in `dd-chain-explorer`.

- Remove `_extract_cw_log_events` UDF from `b_app_logs_data` table definition
- Switch `cloudFiles.format` from `binaryFile` to `json`
- Validate DEV pipeline: `b_app_logs_data` row count increases; `s_logs.logs_streaming`,
  `s_logs.logs_batch`, and Gold MVs `g_api_keys.*` still pass expectations

**Why parallel:** this fix can be developed while WP-1/WP-2 build the new stack, but
must be deployed to DEV before the DEV cutover gate in WP-5 (SC-09).

---

## WP-1 — Repository and Library Foundation (`dd-chain-capture`)

**Owner:** software-engineer-python
**Repo:** new `dd-chain-capture` GitHub repository
**No blocking dependency beyond WP-0.1 resolved**

### WP-1.1 — Scaffold repository structure

Create the canonical directory tree:
```
dd-chain-capture/
├── schemas/          ← Avro .avsc files
├── lib/dm_capture_utils/
├── apps/job1..job5/  ← entrypoint packages
├── infra/aws/        ← Terraform: ECR + IAM
├── infra/kafka-connect/
│   ├── Dockerfile
│   ├── connectors/   ← 3 connector JSON configs
│   └── scripts/
├── docker/
├── docker-compose.yml
├── .env.dev / .env.hml / .env.prod (gitignored)
└── .github/workflows/
```

Commit conventions, `.gitignore`, `pyproject.toml`/`setup.py` for `dm_capture_utils`,
ECR Terraform resources (`dd-chain-capture-stream`, `dd-chain-capture-connect`).

### WP-1.2 — Author `dm_capture_utils` package

Five modules. Namespace convention: `com.ddchain.capture.<entity>`.

| Module | Responsibilities |
|--------|-----------------|
| `dm_kafka.py` | `KafkaProducer`/`KafkaConsumer` wrappers with Avro serialization via Confluent Schema Registry |
| `dm_avro_schemas.py` | `.avsc` loader, Schema Registry auto-registration at startup, `FULL` compatibility enforcement |
| `dm_redis.py` | `RedisCache` class: BLOCK_CACHE (`HASH`, TTL=3600s), SEMAPHORE (`SET NX EX 60` + Lua release), ABI/ABI_NEG caches |
| `api_keys_manager.py` | Round-robin election (`replica_id % len(keys)`) + Redis SETNX lock; no DynamoDB dependency (ADR-CAPTURE-003) |
| `dm_structured_logger.py` | Structured stdout logger compatible with Fluent Bit collection |

Retained from `dm-chain-utils==0.2.9` (pip dependency, not re-implemented): `dm_parameter_store`, `dm_web3_client`, `dm_etherscan`.

### WP-1.3 — Write Avro schemas

Five `.avsc` files under `schemas/`. Constraints from SPEC §2.4:
- All numeric Ethereum fields as `string` (no `long`/`double`)
- Nullable fields: `["null", "string"]` union, `"default": null`
- `TransactionDecoded.avsc` MUST include `block_timestamp` field
- FULL compatibility: all post-v1 fields require defaults

| Schema | Topic subject |
|--------|--------------|
| `MinedBlockEvent.avsc` | `mainnet-mined-blocks-events-value` |
| `BlockTxHashId.avsc` | `mainnet-block-txs-hash-id-value` |
| `TransactionData.avsc` | `mainnet-transactions-data-value` |
| `BlockData.avsc` | `mainnet-blocks-data-value` |
| `TransactionDecoded.avsc` | `mainnet-transactions-decoded-value` |

### WP-1.4 — Unit tests for `dm_capture_utils`

pytest suite covering: Avro round-trip (serialize → deserialize), Redis SEMAPHORE Lua
script (acquire/release/expiry), round-robin API key election with 6 replicas, schema
registration mock. CI gate: `pytest lib/dm_capture_utils/tests/ -v`.

---

## WP-2 — Confluent Platform + Redis Infrastructure

**Owner:** devops-engineer
**Parallel with WP-1. Must complete before WP-3 begins testing against live infra.**

### WP-2.1 — Custom Kafka Connect Docker image

Base: `confluentinc/cp-kafka-connect:7.6.0`. Add:
- `confluentinc/kafka-connect-s3:10.5.x` plugin (installed via Confluent Hub)
- `aws_signing_helper` binary bundled in image (pinned version — not bind-mounted)

Image name: `dd-chain-capture-connect`. Pushed to ECR `dd-chain-capture-connect` repo.

**Security constraint:** `aws_signing_helper` is in the image. AWS credentials enter
only via `env_file: /etc/dd-chain-capture/aws.env` — NEVER in `environment:` or
`secrets:` blocks.

### WP-2.2 — Docker Compose configuration

Single `docker-compose.yml` for all environments (DEV/HML/PROD), parameterized by
`.env.{env}`. 14 services:

| Service group | Services |
|--------------|---------|
| Confluent Platform | broker (KRaft), schema-registry, connect, connector-init, control-center |
| Coordination | redis |
| Log shipping | fluent-bit |
| Capture jobs | job-mined-blocks-watcher, job-orphan-blocks-watcher, job-block-data-crawler, job-mined-txs-crawler (×6 via --scale), job-txs-input-decoder (×3 via --scale) |

**Port exposure rule:** No `ports:` declaration except SSH tunnel access for control-center
(9021 host-only, localhost bind). Kafka (9092), Schema Registry (8081), Connect (8083),
Redis (6379) are container-network-only.

Redis config (applied via command or config file):
```
save ""
appendonly no
maxmemory 256mb
maxmemory-policy allkeys-lru
requirepass ${REDIS_PASSWORD}
```

### WP-2.3 — Kafka Connect S3 Sink Connector configurations

Three JSON connector configs under `infra/kafka-connect/connectors/`. Critical settings
(per ADR-CAPTURE-008 and data-engineer F-001):

```json
{
  "connector.class": "io.confluent.connect.s3.S3SinkConnector",
  "topics.dir": "raw",
  "partitioner.class": "io.confluent.connect.storage.partitioner.TimeBasedPartitioner",
  "path.format": "'year'=YYYY/'month'=MM/'day'=dd/'hour'=HH",
  "timestamp.extractor": "Record",
  "format.class": "io.confluent.connect.s3.format.json.JsonFormat",
  "value.converter": "io.confluent.connect.avro.AvroConverter",
  "value.converter.schema.registry.url": "http://schema-registry:8081",
  "value.converter.schemas.enable": "false",
  "s3.region": "sa-east-1",
  "storage.class": "io.confluent.connect.s3.storage.S3Storage"
}
```

Each connector has a dedicated DLQ topic. `register-connectors.sh` calls Kafka Connect
REST API (`POST /connectors`) after the broker and connect service are healthy.

### WP-2.4 — IAM Roles Anywhere setup

Manual operator steps (documented as runbook in `infra/aws/iam-roles-anywhere-runbook.md`):
1. OpenSSL CA key generation on operator machine (`ca.key` + `ca.crt` — CA key NEVER on VPS)
2. VPS certificate issuance (`vps.crt` + `vps.key`)
3. AWS Trust Anchor creation (Terraform resource in `infra/aws/iam-capture-user.tf`)
4. IAM role with minimum policy (SSM + S3 `raw/*` + ECR pull)
5. VPS: install `aws_signing_helper`, create `/etc/dd-chain-capture/` (`chmod 700`),
   configure credential refresh cron (every 50 minutes), restart Connect post-refresh

**IAM scope per container type (ADR-CAPTURE-001):**
- Python job containers: `ssm:GetParametersByPath` + ECR pull. No S3 write.
- Kafka Connect container: `s3:PutObject` + `s3:AbortMultipartUpload` + `s3:ListMultipartUploadParts` on `raw/*` only. No SSM.

---

## WP-3 — Capture Job Adaptation (Python)

**Owner:** software-engineer-python
**Dependency:** WP-1 (library) complete; WP-2 (infra) running in DEV

Each job replaces its AWS managed-service calls with `dm_capture_utils` equivalents.
Python jobs have NO S3 write permission post-migration (ADR-CAPTURE-008).

### WP-3.1 — Job 1: MinedBlocksWatcher

Replace: Kinesis producer (`dm_kinesis.KinesisProducer`)
With: `dm_kafka.KafkaProducer` producing Avro `MinedBlockEvent` to `mainnet-mined-blocks-events` (4 partitions)

### WP-3.2 — Job 2: OrphanBlocksWatcher

Replace: SQS consumer + DynamoDB BLOCK_CACHE read/write
With: Kafka consumer (`orphan-watcher-cg`) from `mainnet-mined-blocks-events` + `dm_redis.RedisCache` BLOCK_CACHE (HASH, TTL=3600s)

Reorg detection: when block hash mismatch detected, re-produces event to `mainnet-mined-blocks-events` to trigger re-crawl.

### WP-3.3 — Job 3: BlockDataCrawler

Replace: Kinesis producer + `boto3.put_object` (direct S3 write)
With: Kafka consumer (`block-crawler-cg`) from `mainnet-mined-blocks-events` + two Kafka producers:
- `mainnet-blocks-data` (4 partitions, Avro `BlockData`) — consumed by S3 Sink Connector 1
- `mainnet-block-txs-hash-id` (6 partitions, Avro `BlockTxHashId`) — inter-job routing

### WP-3.4 — Job 4: MinedTxsCrawler

Replace: Kinesis producer + DynamoDB SEMAPHORE
With: Kafka consumer (`txs-crawler-cg`, 1 partition per replica × 6) + Redis SETNX round-robin election + `KafkaProducer` to `mainnet-transactions-data` (6 partitions, Avro `TransactionData`)

SEMAPHORE: `SET semaphore:{api_key_name} {process_id} NX EX 60`. Release via Lua script.
Round-robin: `api_key = keys[replica_id % len(keys)]`.

### WP-3.5 — Job 5: TxsInputDecoder

Replace: Kinesis producer + DynamoDB ABI cache + `boto3.put_object`
With: Kafka consumer (`txs-decoder-cg`, 2 partitions per replica × 3) + `dm_redis.RedisCache` ABI/ABI_NEG + `KafkaProducer` to `mainnet-transactions-decoded` (6 partitions, Avro `TransactionDecoded`)

`TransactionDecoded.avsc` MUST include `block_timestamp` field (required by S3 Sink Connector 3 and forward compatibility — ADR-CAPTURE-008).

### WP-3.6 — Fluent Bit configuration

Configure `fluent-bit` service to collect stdout/stderr from all job containers via Docker
log driver, and deliver plain NDJSON to:
```
s3://dm-chain-explorer-raw-data/raw/app_logs/year=YYYY/month=MM/day=DD/hour=HH/
```

Fluent Bit uses IAM credentials from `/etc/dd-chain-capture/aws.env` (same credential
model as Kafka Connect). Output plugin: `s3` with `time_key_format` matching the
`year=/month=/day=/hour=` Hive partition convention.

---

## WP-4 — CI/CD and Deployment

**Owner:** devops-engineer
**Parallel with WP-1/WP-2/WP-3 for authoring; deployment gates require WP-3 complete**

### WP-4.1 — GitHub Actions `ci.yml`

Triggers: PR to main.
Steps:
1. ruff lint (`lib/`, `apps/`)
2. pytest (`lib/dm_capture_utils/tests/`)
3. hadolint (`infra/kafka-connect/Dockerfile`)

No AWS credentials in CI. Exit non-zero on any failure.

### WP-4.2 — GitHub Actions `deploy.yml`

Triggers: push to main (merge).
Steps:
1. OIDC auth → ECR `GetAuthorizationToken`
2. Build + push `dd-chain-capture-stream` image (tagged `sha-<commit>`)
3. Build + push `dd-chain-capture-connect` image (tagged `sha-<commit>`)
4. HML deploy: SSH to VPS, `docker compose --env-file .env.hml up -d --scale job-mined-txs-crawler=6 --scale job-txs-input-decoder=3 --no-build` (automatic)
5. PROD deploy: same command with `.env.prod` — requires manual approval gate in Actions

OIDC IAM role: ECR push to `dd-chain-capture-stream` and `dd-chain-capture-connect` only. No S3, SSM, or DynamoDB.

### WP-4.3 — VPS setup runbook

Document in `infra/vps-setup-runbook.md`:
1. Docker Engine install (`apt install docker-ce`)
2. Create `deploy` service user, add to `docker` group
3. Clone repo to `/opt/dd-chain-capture`
4. Create `/etc/dd-chain-capture/` (`chmod 700`, owned by `deploy`)
5. Install `aws_signing_helper` (version-pinned)
6. Configure credential refresh cron: every 50 min → write to `/etc/dd-chain-capture/aws.env` (`chmod 600`) + `docker compose restart connect`
7. Hostinger firewall rules: deny all inbound except SSH (22); no port 9092/8081/8083/6379/9021 exposure

---

## WP-5 — Integration Validation and Cutover

**Owner:** devops-engineer (infra/cutover), data-engineer (Databricks validation)
**Dependency:** WP-0.2 deployed, WP-3 complete, WP-4 deployed to HML

### WP-5.1 — DEV integration gate

1. Bring up full stack on VPS DEV environment
2. Confirm all 14 containers healthy (`docker compose ps`)
3. Confirm Schema Registry shows 5 subjects; compatibility = FULL
4. Confirm 3 connectors in `RUNNING` state
5. Trigger `dlt_ethereum` DEV pipeline; verify `b_ethereum.eth_mined_blocks`, `eth_transactions`, `eth_txs_input_decoded` Bronze tables receive rows
6. Verify S3 path: `raw/{stream}/year=Y/month=M/day=D/hour=H/` — matches Firehose convention (SC-06)
7. Validate `b_app_logs_data` receives Fluent Bit NDJSON (SC-09; requires WP-0.2 deployed)

### WP-5.2 — Kafka UI (replace Control Center before PROD)

Replace `confluentinc/cp-enterprise-control-center:7.6.0` with `provectuslabs/kafka-ui:latest`
(MIT license, ~100 MB RAM) in `docker-compose.yml`. Control Center has 30-day trial limit
and must be removed before PROD go-live (ADR-CAPTURE-009, SC-13). Kafka UI provides topic
browsing, consumer lag, and connector status without license concerns.

### WP-5.3 — ECS decommission sequence

Ordered decommission to prevent data gap:
1. Confirm VPS stack is producing to S3 (monitored for ≥24h)
2. Stop ECS tasks: set desired count = 0 on all capture services
3. Confirm S3 landing continues from Kafka Connect (no gap in `raw/mainnet-*/`)
4. Decommission ECS task definitions (set inactive / delete)
5. Delete Kinesis Data Streams (after 7-day monitoring window)
6. Delete Firehose delivery streams
7. Remove SQS queues
8. Remove DynamoDB hot entities (`BLOCK_CACHE`, `SEMAPHORE`, `ABI`, `ABI_NEG` key patterns)

### WP-5.4 — PROD cutover

Blue/green switch: VPS produces while ECS is still at desired=0 (not yet deleted).
Rollback plan: if VPS fails within 24h, set ECS desired count back to previous values
(ECS task definitions still exist). After 24h stable, proceed with WP-5.3 decommission.

---

## Architecture Decisions (this release)

All ADRs are documented in SPEC.md §5. Key implementation constraints:

- **IAM Roles Anywhere (ADR-CAPTURE-001):** CA key stays on operator machine. VPS holds
  only issued certs. Connect restarts every 50 min for credential refresh.
- **Redis memory-only (ADR-CAPTURE-002):** No persistence. BLOCK_CACHE warm-up ≤1h after
  restart. ABI warm-up ~30–60 min (Etherscan API cold start). Acceptable trade-off.
- **Round-robin API key election (ADR-CAPTURE-003):** No DynamoDB access from VPS. Redis
  SETNX only.
- **Three S3 Sink Connectors (ADR-CAPTURE-008):** `mainnet-transactions-data` is both an
  inter-job routing topic and an S3 delivery topic. A dedicated third connector with its own
  consumer group is required.
- **Connector path config (F-001 critical):** `topics.dir=raw` + `TimeBasedPartitioner` +
  `path.format='year'=YYYY/...` is non-negotiable. Without it, Auto Loader reads 0 records.
- **Control Center trial (ADR-CAPTURE-009):** Must be replaced with Kafka UI before PROD
  go-live. SC-13 is a hard gate.

## Technical Risks

| Risk | Mitigation |
|------|-----------|
| Connector path misconfiguration (HIGH/HIGH) | DEV validation is explicit gate before HML/PROD |
| Control Center trial expiry | SC-13 mandates Kafka UI replacement (WP-5.2) |
| Connect credential refresh pause | 50-min cron; investigate `credential_process` in-container long-term |
| VPS RAM pressure (8 GB minimum) | Remove Control Center in DEV/HML after Kafka UI replaces it |
| `block_timestamp` missing in TransactionDecoded | Schema inspection before first deploy — SPEC constraint |
| Kafka single broker failure | Recovery from chain head; expected downtime < 5 min |

## Validation Plan

Gates in order:
1. **DEV stack health** — `docker compose ps`: all 14 services `running`/`healthy`
2. **Schema Registry** — `curl http://schema-registry:8081/subjects` → 5 subjects; `curl http://schema-registry:8081/config` → `FULL`
3. **Connectors running** — `curl http://connect:8083/connectors/{name}/status` → `RUNNING` (×3)
4. **Auto Loader gate** — `dlt_ethereum` DEV pipeline Bronze tables gain rows (SC-04/SC-05)
5. **S3 path gate** — `aws s3 ls s3://dm-chain-explorer-raw-data/raw/mainnet-blocks-data/ --recursive | head -5` confirms `year=/.../` pattern
6. **app_logs gate** — `b_app_logs_data` gains rows from Fluent Bit NDJSON (SC-09)
7. **PROD cutover** — blue/green switch with 24h monitoring before ECS decommission
