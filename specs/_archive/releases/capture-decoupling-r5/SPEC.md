# SPEC — Release capture-decoupling-r5

**Release ID:** capture-decoupling-r5
**Status:** Aprovado
**Owner:** product-engineer
**Created:** 2026-05-23

---

## 1. Goal

Migrate the DD Chain Explorer capture layer from AWS managed services (ECS Fargate + SQS + Kinesis Data Streams + Kinesis Firehose + DynamoDB hot entities) to a self-hosted Hostinger VPS running the full Confluent Platform stack (Kafka KRaft + Schema Registry + Kafka Connect + Control Center) plus Redis. The new implementation lives in a new repository `dd-chain-capture`. The S3 integration boundary remains frozen: Databricks Auto Loader, DLT pipelines, and all downstream analytics are untouched.

---

## 2. Scope In

### 2.1 Infrastructure

- Provision a Hostinger VPS (minimum 8 GB RAM / 4 vCPU / 60 GB SSD; recommended 16 GB / 8 vCPU).
- Create new GitHub repository `dd-chain-capture`.
- Create two ECR repositories in the existing AWS account (`sa-east-1`):
  - `dd-chain-capture-stream` — Python capture jobs image.
  - `dd-chain-capture-connect` — Custom Kafka Connect image with S3 Sink plugin.
- Set up OIDC IAM role for GitHub Actions CI (ECR push only; no S3 or SSM access from CI).
- Configure IAM Roles Anywhere Trust Anchor using a self-signed OpenSSL CA (operator machine; see ADR-CAPTURE-001).
- Create VPS IAM role with the minimum policy: `ssm:GetParametersByPath` on API key paths, `s3:PutObject` + `s3:AbortMultipartUpload` + `s3:ListMultipartUploadParts` on `raw/*` prefix only, `ecr:GetAuthorizationToken` + `ecr:BatchGetImage` + `ecr:GetDownloadUrlForLayer` on both ECR repos.
- VPS one-time setup: install Docker Engine, create `deploy` service user, create `/etc/dd-chain-capture/` credential directory (`chmod 700`), install `aws_signing_helper`, configure credential refresh cron job (every 50 minutes), clone repo to `/opt/dd-chain-capture`.

### 2.2 Confluent Platform Stack (14 containers total on VPS)

All environments (DEV / HML / PROD) use the same `docker-compose.yml` differentiated only by `.env.dev` / `.env.hml` / `.env.prod`.

| Service | Image | Role |
|---------|-------|------|
| broker | `confluentinc/cp-kafka:7.6.0` | Kafka broker, KRaft mode (no ZooKeeper), single node |
| schema-registry | `confluentinc/cp-schema-registry:7.6.0` | Avro Schema Registry |
| connect | Custom image (cp-kafka-connect:7.6.0 + S3 plugin) | Kafka Connect worker with S3 Sink Connectors |
| control-center | `confluentinc/cp-enterprise-control-center:7.6.0` | Management UI (SSH tunnel access only; trial 30 days) |
| redis | `redis:7-alpine` | Coordination store (BLOCK_CACHE, SEMAPHORE, ABI caches) |
| fluent-bit | `fluent/fluent-bit:3.0` | Log shipping: Docker stdout/stderr → S3 `raw/app_logs/` |
| connector-init | `curlimages/curl:8.7.1` | One-shot container: registers S3 Sink connectors on startup |
| job-mined-blocks-watcher | `dd-chain-capture-stream:<sha>` | Job 1 (1 replica) |
| job-orphan-blocks-watcher | `dd-chain-capture-stream:<sha>` | Job 2 (1 replica) |
| job-block-data-crawler | `dd-chain-capture-stream:<sha>` | Job 3 (1 replica) |
| job-mined-txs-crawler | `dd-chain-capture-stream:<sha>` | Job 4 (6 replicas) |
| job-txs-input-decoder | `dd-chain-capture-stream:<sha>` | Job 5 (3 replicas) |
| connector-s3-blocks | managed by connect | S3 Sink Connector 1: `mainnet-blocks-data` → `raw/mainnet-blocks-data/` |
| connector-s3-txs-data | managed by connect | S3 Sink Connector 2: `mainnet-transactions-data` → `raw/mainnet-transactions-data/` |
| connector-s3-txs-decoded | managed by connect | S3 Sink Connector 3: `mainnet-transactions-decoded` → `raw/mainnet-transactions-decoded/` |

**Port exposure rule:** No container exposes ports to the host except via SSH tunnel (Control Center on 9021). Kafka (9092), Schema Registry (8081), Kafka Connect (8083), Redis (6379) are internal only. Docker iptables bypass means any `ports:` declaration exposes services to the internet — this is forbidden.

### 2.3 Kafka Topology (5 topics + 3 DLQ topics)

Avro serialization on all topics. TopicNameStrategy for schema subjects (`{topic}-value`). All topics: `replication.factor=1`, `min.insync.replicas=1` (single-broker constraint).

| Topic | Role | Partitions | Retention time | Retention size | Producer | Consumer group(s) |
|-------|------|-----------|----------------|----------------|----------|-------------------|
| `mainnet-mined-blocks-events` | Inter-job routing | 4 | 2h | 512 MB | Job 1 | `orphan-watcher-cg` (Job 2), `block-crawler-cg` (Job 3) |
| `mainnet-block-txs-hash-id` | Inter-job routing | 6 | 2h | 2 GB | Job 3 | `txs-crawler-cg` (Job 4 ×6) |
| `mainnet-transactions-data` | Inter-job routing + S3 sink | 6 | 4h | 8 GB | Job 4 ×6 | `txs-decoder-cg` (Job 5 ×3), `connect-s3-sink-txs-data` |
| `mainnet-blocks-data` | S3 delivery only | 4 | 4h | 2 GB | Job 3 | `connect-s3-sink-blocks` |
| `mainnet-transactions-decoded` | S3 delivery only | 6 | 4h | 8 GB | Job 5 ×3 | `connect-s3-sink-txs-decoded` |
| `s3-sink-blocks-dlq` | Dead-letter | 1 | 7d | — | Kafka Connect | — |
| `s3-sink-txs-data-dlq` | Dead-letter | 1 | 7d | — | Kafka Connect | — |
| `s3-sink-txs-decoded-dlq` | Dead-letter | 1 | 7d | — | Kafka Connect | — |

**Schema Registry compatibility:** `FULL` (prevents both field removal and silent consumer breakage). Set globally via `PUT /config {"compatibility": "FULL"}` on first deployment.

**Correction from v2 data-engineer report (F-001 CRITICAL):** Connectors MUST use:
- `topics.dir=raw` (overrides default `topics/` prefix)
- `partitioner.class=io.confluent.connect.storage.partitioner.TimeBasedPartitioner`
- `path.format='year'=YYYY/'month'=MM/'day'=dd/'hour'=HH`
- `timestamp.extractor=Record` (Kafka record timestamp — NOT `RecordField` on the routing topics)

Without this, Auto Loader reads 0 records. Validated in DEV before HML/PROD cutover.

**S3 Sink Connector 3 (raw transactions) — CRITICAL finding from data-engineer report:** `b_ethereum.eth_transactions` Bronze table reads from `raw/mainnet-transactions-data/`. A third S3 Sink Connector is REQUIRED. Job 4 already produces to `mainnet-transactions-data` (inter-job routing). The connector reads this same topic with consumer group `connect-s3-sink-txs-data` and delivers to `s3://dm-chain-explorer-raw-data/raw/mainnet-transactions-data/year=Y/month=M/day=D/hour=H/`.

### 2.4 Python Library `dm_capture_utils` in `dd-chain-capture`

New repository `dd-chain-capture` contains:

```
dd-chain-capture/
├── schemas/
│   ├── MinedBlockEvent.avsc
│   ├── BlockTxHashId.avsc
│   ├── TransactionData.avsc        (RawTransaction — also feeds S3 via connector 2)
│   ├── BlockData.avsc
│   └── TransactionDecoded.avsc     (must include block_timestamp field)
├── lib/dm_capture_utils/
│   ├── dm_kafka.py                 # Avro-aware KafkaProducer / KafkaConsumer
│   ├── dm_avro_schemas.py          # Schema loader + Schema Registry registrar
│   ├── dm_redis.py                 # RedisCache: BLOCK_CACHE, SEMAPHORE, ABI/ABI_NEG
│   ├── api_keys_manager.py         # Round-robin + Redis SETNX (no DynamoDB)
│   ├── dm_web3_client.py
│   ├── dm_etherscan.py
│   └── dm_structured_logger.py
├── apps/                           # Job 1-5 entrypoints
│   ├── job1_mined_blocks_watcher/
│   ├── job2_orphan_blocks_watcher/
│   ├── job3_block_data_crawler/
│   ├── job4_mined_txs_crawler/
│   └── job5_txs_input_decoder/
├── infra/
│   ├── aws/iam-capture-user.tf
│   └── kafka-connect/
│       ├── Dockerfile              # cp-kafka-connect:7.6.0 + S3 plugin
│       ├── connectors/             # 3 connector JSON configs
│       └── scripts/register-connectors.sh
├── docker-compose.yml
├── .env.dev / .env.hml / .env.prod (gitignored)
└── .github/workflows/ci.yml + deploy.yml
```

**dm-chain-utils boundary:**

**Retained from `dm-chain-utils==0.2.9`** (remain as pip dependency): `dm_parameter_store`, `dm_web3_client`, `dm_etherscan`, `dm_cloudwatch_logger` (kept for logging compatibility during transition).

**NOT used in new capture jobs** (their functionality is replaced by `dm_capture_utils`): `dm_kinesis`, `dm_sqs`, `dm_firehose`, `dm_dynamodb`. These modules remain in `dm-chain-utils` for the analytics layer (Lambda functions, Databricks jobs) — they are NOT removed from the package.

**Schema constraints:**
- `TransactionDecoded.avsc` MUST include `block_timestamp` field (required for hourly S3 partitioning by connector).
- All numeric Ethereum fields typed as `string` in Avro (no `long`/`double` — overflow risk).
- Nullable fields use `["null", "string"]` union with `"default": null`.
- All fields added after v1 must have a `default` value (FULL compatibility requirement).

**Avro namespace convention:** `com.ddchain.capture.<entity>` (e.g., `com.ddchain.capture.mined_block_event`, `com.ddchain.capture.transaction_data`). All `.avsc` files in `schemas/` use this namespace.

**IAM scope per container type:**
- Python job containers: `ssm:GetParametersByPath` + ECR pull. No S3 write permission.
- Kafka Connect container: `s3:PutObject` + `s3:AbortMultipartUpload` + `s3:ListMultipartUploadParts` on `raw/*` only. No SSM.

### 2.5 Redis (Coordination Store)

Redis single-node, memory-only, no persistence. Config:
- `save ""` (RDB disabled)
- `appendonly no` (AOF disabled)
- `maxmemory 256mb`
- `maxmemory-policy allkeys-lru`
- `requirepass ${REDIS_PASSWORD}` (non-empty in all environments)
- No volume mount (transient by design)

Entity mapping:

| Entity | Redis key pattern | TTL | Data structure |
|--------|------------------|-----|----------------|
| BLOCK_CACHE | `block_cache:{block_number}` | 3600s | HASH (field: `block_hash`) |
| SEMAPHORE | `semaphore:{api_key_name}` | 60s | STRING (`SET NX EX 60`) |
| ABI | `abi:{contract_address}` | None (LRU eviction) | HASH (field: `abi_json`) |
| ABI_NEG | `abi_neg:{contract_address}` | 86400s | STRING (value: `1`) |

SEMAPHORE release: Lua script comparing stored value to caller's process_id before `DEL`.

DynamoDB entities NOT migrated (remain in AWS): `CONTRACT`, `CONSUMPTION`, `COUNTER` (cloud-boundary, written by Lambda functions).

### 2.6 Security

- **Kafka broker:** listeners bind to `PLAINTEXT://broker:9092` (container-name DNS only). No `ports:` mapping for port 9092. Unauthenticated PLAINTEXT is acceptable for intra-VPS traffic (no external exposure). SSL/SASL deferred to post-go-live hardening.
- **Control Center:** no `ports:` mapping for port 9021. Access via SSH tunnel only: `ssh -N -L 9021:control-center:9021 deploy@<vps-ip>`. Control Center must be replaced with Kafka UI (Provectus, MIT license) before PROD go-live (trial expires 30 days after first deployment).
- **AWS credentials on VPS:** IAM Roles Anywhere (PROD) — `aws_signing_helper credential-process` refreshes STS token every 50 minutes; credentials written to `/etc/dd-chain-capture/aws.env` (`chmod 600`, owned by service user). Kafka Connect container is restarted after each credential refresh (env_file is read only at container start).
- **CA key rule:** OpenSSL self-signed CA key (`ca.key`) lives on the operator's machine ONLY. Never on the VPS. VPS holds `vps.crt` + `vps.key` (issued by the CA, not the CA key itself). Violation defeats the short-lived credential model entirely.
- **Docker credential rule:** AWS credentials must NEVER appear in `environment:` or `secrets:` blocks in `docker-compose.yml`. The only accepted injection mechanism is `env_file: /etc/dd-chain-capture/aws.env`.
- **`aws_signing_helper` location:** bundled in the Kafka Connect Docker image (not bind-mounted). This ensures the binary is version-pinned and auditable.

### 2.7 DevOps / CI-CD

- **GitHub CI workflow:** `ci.yml` triggers on PR — lint (ruff) + unit tests (pytest) + Dockerfile lint (hadolint). No AWS credentials.
- **GitHub Deploy workflow:** `deploy.yml` triggers on merge to main — OIDC auth, builds and pushes both images to ECR, deploys to HML via SSH, deploys to PROD via SSH with manual approval gate.
- **OIDC IAM role for CI:** ECR push to `dd-chain-capture-stream` and `dd-chain-capture-connect` only. No S3, SSM, or DynamoDB access.
- **VPS deploy command:** `docker compose --env-file .env.{env} up -d --scale job-mined-txs-crawler=6 --scale job-txs-input-decoder=3 --no-build`.

### 2.8 dm-app-logs DLT Fix (scope item in dd-chain-explorer)

Fluent Bit on the VPS writes plain NDJSON to `raw/app_logs/year=Y/month=M/day=D/hour=H/`. The current Bronze `b_app_logs_data` in `dd-chain-explorer` uses `cloudFiles.format=binaryFile` with a CloudWatch envelope UDF (`_extract_cw_log_events`) that expects double-gzipped CW Logs format. This is incompatible with Fluent Bit's plain NDJSON output.

**Required fix in `dd-chain-explorer` (DABs `dlt_app_logs`):**
- Remove `_extract_cw_log_events` UDF
- Switch `_auto_loader_cwlogs()` to `cloudFiles.format=json`
- Validate `s_logs.logs_streaming`, `s_logs.logs_batch`, and Gold MVs still pass (Silver logic parses the `message` field string — unchanged)

This fix MUST land before the capture layer cutover to VPS. It is a dependency of this release (see Section 7).

---

## 3. Scope Out

The following are explicitly out of scope for this release:

- **Databricks DLT pipelines** (`dm-ethereum`, `dm-app-logs` beyond the Bronze UDF fix): no changes to Silver/Gold logic, materialized views, or Unity Catalog schemas.
- **Gold Materialized Views** and Lakeview Dashboards: untouched.
- **Lambda functions** (`gold_to_dynamodb`, `contracts_ingestion`): remain in `dd-chain-explorer`, unchanged.
- **DynamoDB cold entities** (`CONTRACT`, `CONSUMPTION`, `COUNTER`, `BLOCK_CACHE` in dd-chain-explorer): the DynamoDB table remains; cold entities are not migrated.
- **Auto Loader configuration changes**: S3 path convention is frozen. No DLT Auto Loader checkpoint resets are expected (path is identical).
- **Kafka SSL/SASL authentication**: deferred post go-live. PLAINTEXT on internal Docker network is acceptable initially.
- **Kafka replication factor > 1**: single-broker VPS; RF=1 throughout. HA upgrade deferred.
- **REST API** (`rest-api-r5`): separate planning session, separate release.
- **CI/CD migration of `dd-chain-explorer` from static AWS keys to OIDC**: flagged as a separate task (not blocked by this release, but should be addressed).
- **Kafka UI (Provectus)** full setup: replacement of Control Center is a task within this release (before PROD go-live), but the Kafka UI is not a new feature — it is a licensing obligation.

---

## 4. Architecture Diagram (Target State)

```
Ethereum Mainnet (RPC via Alchemy / Infura — SSM keys)
    │
    ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  HOSTINGER VPS — Docker Compose (DEV) / docker compose --scale (HML/PROD)             │
│  [min 8 GB RAM / 4 vCPU / 60 GB SSD — recommended 16 GB / 8 vCPU]                     │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │  CONFLUENT PLATFORM 7.6.x (JVM containers, ~2.3 GB baseline)                    │   │
│  │                                                                                   │   │
│  │  broker (cp-kafka KRaft, no ZooKeeper)                                           │   │
│  │    Topics: mainnet-mined-blocks-events (4p/2h)                                   │   │
│  │            mainnet-block-txs-hash-id   (6p/2h)                                   │   │
│  │            mainnet-transactions-data   (6p/4h) ← also consumed by S3 connector   │   │
│  │            mainnet-blocks-data         (4p/4h) ← S3 delivery only                │   │
│  │            mainnet-transactions-decoded(6p/4h) ← S3 delivery only                │   │
│  │            s3-sink-blocks-dlq  / s3-sink-txs-data-dlq / s3-sink-txs-decoded-dlq (DLQ, 7d) │   │
│  │                                                                                   │   │
│  │  schema-registry (port 8081 — internal only)                                      │   │
│  │    Subjects: mainnet-mined-blocks-events-value    (MinedBlockEvent)               │   │
│  │              mainnet-block-txs-hash-id-value      (BlockTxHashId)                 │   │
│  │              mainnet-transactions-data-value      (TransactionData/RawTransaction) │   │
│  │              mainnet-blocks-data-value            (BlockData)                     │   │
│  │              mainnet-transactions-decoded-value   (TransactionDecoded)            │   │
│  │    Compatibility: FULL (global)                                                   │   │
│  │                                                                                   │   │
│  │  connect (port 8083 — internal only)                                              │   │
│  │    Custom image: cp-kafka-connect:7.6.0 + confluentinc/kafka-connect-s3:10.5.x  │   │
│  │    aws_signing_helper bundled in image                                            │   │
│  │    Credentials: /etc/dd-chain-capture/aws.env (env_file, chmod 600)              │   │
│  │    Connectors:                                                                    │   │
│  │      s3-sink-blocks     ← mainnet-blocks-data         → raw/mainnet-blocks-data/ │   │
│  │      s3-sink-txs-data   ← mainnet-transactions-data   → raw/mainnet-transactions-data/ │   │
│  │      s3-sink-txs-decoded← mainnet-transactions-decoded→ raw/mainnet-txs-decoded/ │   │
│  │    All connectors: topics.dir=raw, TimeBasedPartitioner,                         │   │
│  │                    path.format='year'=YYYY/'month'=MM/'day'=dd/'hour'=HH         │   │
│  │                    timestamp.extractor=Record, format.class=JsonFormat            │   │
│  │                    value.converter=AvroConverter, schemas.enable=false            │   │
│  │                                                                                   │   │
│  │  control-center (port 9021 — SSH tunnel access only; replace with Kafka UI       │   │
│  │    Provectus MIT before PROD go-live — 30-day trial limit)                       │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
│  ┌──────────────────────┐    ┌─────────────────────────────────────────────────────┐   │
│  │  redis:7-alpine       │    │  CAPTURE JOBS (Python, Avro serialization)          │   │
│  │  Memory-only, no AOF  │    │                                                      │   │
│  │  maxmemory 256 MB     │    │  Job 1: MinedBlocksWatcher (×1)                     │   │
│  │  block_cache TTL=1h   │    │    polls eth_getBlock → Kafka mainnet-mined-blocks  │   │
│  │  semaphore TTL=60s    │    │                                                      │   │
│  │  abi / abi_neg cache  │    │  Job 2: OrphanBlocksWatcher (×1)                   │   │
│  └──────────────────────┘    │    consumer orphan-watcher-cg → Redis BLOCK_CACHE    │   │
│                               │    re-produces reorgs → mainnet-mined-blocks         │   │
│  ┌──────────────────────┐    │                                                      │   │
│  │  fluent-bit:3.0       │    │  Job 3: BlockDataCrawler (×1)                      │   │
│  │  Docker stdout/stderr │    │    consumer block-crawler-cg                        │   │
│  │  → S3 raw/app_logs/   │    │    produces → mainnet-blocks-data (S3 sink)         │   │
│  │  IAM creds from       │    │    produces → mainnet-block-txs-hash-id (routing)   │   │
│  │  /etc/.../aws.env     │    │                                                      │   │
│  └──────────────────────┘    │  Job 4: MinedTxsCrawler (×6)                       │   │
│                               │    consumer txs-crawler-cg (1 partition each)       │   │
│                               │    Redis SEMAPHORE (round-robin + SETNX TTL 60s)    │   │
│                               │    produces → mainnet-transactions-data              │   │
│                               │               (routing + S3 sink connector 2)        │   │
│                               │                                                      │   │
│                               │  Job 5: TxsInputDecoder (×3)                       │   │
│                               │    consumer txs-decoder-cg (2 partitions each)      │   │
│                               │    Redis ABI/ABI_NEG cache                          │   │
│                               │    Etherscan API for ABI retrieval (SSM keys)       │   │
│                               │    produces → mainnet-transactions-decoded (S3 sink) │   │
│                               └─────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────────────┘
     │
     │  Kafka Connect S3 Sink (3 connectors)
     │  FORMAT: NDJSON (JsonFormat output — Avro decoded by AvroConverter, schema envelope removed)
     │  PATH FROZEN: raw/{stream-name}/year=YYYY/month=MM/day=DD/hour=HH/
     ▼
┌────────────────────────────────────────────────────────────────────┐
│  AWS S3 — dm-chain-explorer-raw-data (sa-east-1)                    │
│                                                                      │
│  raw/mainnet-blocks-data/year=Y/month=M/day=D/hour=H/*.json         │
│  raw/mainnet-transactions-data/year=Y/month=M/day=D/hour=H/*.json   │
│  raw/mainnet-transactions-decoded/year=Y/month=M/day=D/hour=H/*.json│
│  raw/app_logs/year=Y/month=M/day=D/hour=H/*.ndjson  (Fluent Bit)    │
│  raw/batch/year=Y/month=M/day=D/ (Lambda contracts — unchanged)     │
└────────────────────────────────────────────────────────────────────┘
     │
     │  Auto Loader cloudFiles.format=json (UNCHANGED — path contract frozen)
     ▼
┌────────────────────────────────────────────────────────────────────┐
│  DATABRICKS DLT — UNCHANGED                                          │
│  dm-ethereum: Bronze (b_ethereum.*) → Silver (s_apps.*) → Gold     │
│  dm-app-logs: Bronze (b_app_logs_data, format=json post-fix)        │
│               → Silver → Gold (g_api_keys.*)                        │
│                                                                      │
│  DynamoDB CONSUMPTION (Lambda gold_to_dynamodb — unchanged)         │
└────────────────────────────────────────────────────────────────────┘
```

**S3 Sink path produced by connector (per data-engineer F-001):**
```
raw/mainnet-blocks-data/year=2026/month=05/day=23/hour=14/<topic>+<partition>+<offset>.json
```
Auto Loader is filename-agnostic. `cloudFiles.partitionColumns=""` suppresses Hive partition inference as before.

**Avro-to-JSON serialization chain:**
```
Python Job (dict) → AvroSerializer (5-byte Confluent magic header + Avro bytes) → Kafka
Kafka → Kafka Connect AvroConverter (fetches schema from SR, decodes Avro) → JsonFormat (plain NDJSON, no schema envelope) → S3
S3 → Databricks Auto Loader (format=json) → Bronze Delta table (UNCHANGED)
```

---

## 5. ADRs

### ADR-CAPTURE-001: IAM Roles Anywhere (OpenSSL Self-Signed CA) as AWS Credential Model

**Decision:** The Hostinger VPS uses IAM Roles Anywhere with a self-signed OpenSSL CA (operator machine) to obtain temporary STS credentials for AWS S3 write and SSM read operations. DEV environment uses a long-lived restricted IAM key stored in `/etc/dd-chain-capture/aws.env` (`chmod 600`). Long-lived IAM keys are NEVER placed in Docker `environment:` or `secrets:` blocks.

**Rationale:** Hostinger is non-AWS — EC2 Instance Profile (IMDSv2) is unavailable. IAM Roles Anywhere provides temporary, auto-rotating credentials via X.509 certificates. The constitution prohibits long-lived IAM keys in Docker env vars or secrets. OpenSSL self-signed CA is free; ACM Private CA costs ~$400/month.

**CA key rule:** The CA private key (`ca.key`) must never reside on the VPS. The VPS holds only `vps.crt` + `vps.key` (issued by the CA). Breach of this rule defeats the short-lived credential model entirely.

**aws_signing_helper location:** Bundled in the Kafka Connect Docker image. Not bind-mounted from the VPS filesystem.

**Credential refresh:** Every 50 minutes via cron. After credential refresh, the Kafka Connect container MUST be restarted (it reads env_file only at container start). A devops-engineer task should investigate `credential_process` inside the container as an alternative to eliminate the restart requirement.

**Certificate validity:** 90 days. CA re-issues before expiry.

**Consequences:** Credential refresh requires container restart for Connect. Connect restart is brief (seconds) and low-risk (connector state persists in Kafka internal topics). Python jobs read SSM at startup; they are unaffected by credential refresh.

---

### ADR-CAPTURE-002: Redis Memory-Only (No Persistence)

**Decision:** Redis runs with `save ""` (RDB disabled) and `appendonly no` (AOF disabled). No Docker volume is mounted for Redis. Redis state is purely in-memory and is lost on container restart.

**Rationale:** BLOCK_CACHE (TTL 1h) and SEMAPHORE (TTL 60s) are designed for reconfigurability. On Redis restart, Job 2 rebuilds BLOCK_CACHE from chain events within 1 hour. Job 4 replicas restart without holding any SEMAPHORE — initial state is correct. ABI cache (no TTL, LRU) is a warm-up optimization; cache miss triggers Etherscan API call (acceptable warm-up cost of ~30–60 minutes). Eliminating AOF removes the risk of AOF corruption on unclean shutdown.

**Consequences:** Redis restart causes ABI cache cold start (higher Etherscan API consumption for ~30–60 minutes). Acceptable trade-off vs AOF corruption risk.

---

### ADR-CAPTURE-003: Round-Robin + Redis SETNX API Key Election; VPS Does Not Access DynamoDB

**Decision:** Job 4 (MinedTxsCrawler) elects API keys using round-robin iteration (`replica_id % len(api_keys)`) plus a Redis SETNX lock (`SET semaphore:{key} {process_id} NX EX 60`). The VPS IAM role does NOT include `dynamodb:*`. DynamoDB COUNTER entities (API key usage tracking) remain populated exclusively by the Lambda `gold_to_dynamodb` pipeline.

**Rationale:** The DynamoDB COUNTER entity is updated with hours of lag (via Gold MV → Lambda). Using stale consumption data for key election provides no real benefit. Round-robin is equally effective and eliminates the cross-system dependency. Removing DynamoDB access from the VPS IAM role reduces the blast radius of a VPS compromise.

**Consequences:** API key consumption analytics (via `g_api_keys.*`) remain unchanged — Lambda still writes COUNTER entities. The VPS simply does not read them.

---

### ADR-CAPTURE-004: ECR as Container Registry

**Decision:** Container images for `dd-chain-capture` are stored in Amazon ECR, same AWS account, `sa-east-1` region. Two new repositories: `dd-chain-capture-stream` and `dd-chain-capture-connect`. CI/CD uses OIDC for ECR push (no static CI keys).

**Rationale:** ECR is the established registry for this project (confirmed from `services/prd/07_ecs/locals.tf`). Using the same account and region minimizes network egress costs for image pulls from the VPS. OIDC replaces static CI credentials used in the legacy `dd-chain-explorer` workflows.

**Consequences:** VPS pulls images from ECR using credentials obtained via IAM Roles Anywhere (same credential model as runtime S3/SSM access).

---

### ADR-CAPTURE-005: dm-app-logs DLT Bronze Fix Required Before Capture Cutover

**Decision:** The `dd-chain-explorer` DABs bundle `dlt_app_logs` must be updated before the VPS capture layer goes live. Specifically: remove `_extract_cw_log_events` UDF and switch `cloudFiles.format` from `binaryFile` to `json`. This is a dependency of this release, not an optional cleanup.

**Rationale:** The current Bronze `b_app_logs_data` assumes CloudWatch Logs double-gzip envelope format. Fluent Bit on the VPS writes plain NDJSON. Without this fix, `b_app_logs_data` will fail to parse all log records after cutover, silently breaking the `g_api_keys.*` Gold MVs and Etherscan/Web3 consumption analytics.

**Consequences:** A minor DLT code change is required in `dd-chain-explorer` before the VPS deployment goes live. Silver and Gold MV logic is unaffected (they parse the `message` string field, which is unchanged).

---

### ADR-CAPTURE-006: Confluent Platform 7.6.x as Kafka Stack (KRaft, Single Broker)

**Decision:** Deploy Confluent Platform 7.6.x (`cp-kafka`, `cp-schema-registry`, `cp-kafka-connect`, `cp-enterprise-control-center`). Use KRaft mode (no ZooKeeper). Single broker, `replication.factor=1` throughout.

**Rationale:** CP 7.6 is the active LTS track for the 7.x generation. It includes KRaft production stability, Connect REST API v3 improvements, and Schema Registry 7.6 compatibility APIs. Apache Kafka alone would require a separate Schema Registry deployment — Confluent Platform bundles all required components at a coherent version. Single-broker KRaft eliminates ZooKeeper (saves ~400 MB RAM). Replication factor 1 is acceptable: capture layer data loss from broker failure is tolerable (Ethereum RPC is re-tailable from chain head after recovery).

**Control Center licensing:** `cp-enterprise-control-center` is trial-only (30 days). A task in this release (before PROD go-live) must replace it with Kafka UI (Provectus, MIT license, ~100 MB RAM). This saves ~924 MB RAM and eliminates the license concern.

**Consequences:** Single broker = broker failure causes capture downtime. Acceptable for a pipeline with recovery from chain head. VPS requires minimum 8 GB RAM; 16 GB recommended to accommodate Confluent JVM footprint (~2.3 GB baseline for the 4 JVM containers).

---

### ADR-CAPTURE-007: Avro Serialization with Schema Registry (FULL Compatibility)

**Decision:** All Kafka messages in `dd-chain-capture` use Avro serialization via Confluent Schema Registry. TopicNameStrategy is used for subject naming. Schema Registry global compatibility is set to `FULL` (bidirectional: both BACKWARD and FORWARD).

**Rationale:** Avro provides a schema contract between producers and consumers. Schema Registry enforces compatibility rules, preventing silent data loss. `FULL` compatibility was chosen over `BACKWARD` because: (a) the data-engineer report (F-003) identified that field removal could silently drop all rows from DLT Silver tables via `expect_or_drop` expectations, and (b) the cost of enforcing `FULL` (cannot remove fields without schema versioning) is acceptable for a pipeline where schema governance is internal to one team.

**Avro-to-JSON chain for S3:** Kafka messages are Avro-encoded (wire format). The Kafka Connect S3 Sink Connector deserializes Avro via `AvroConverter` and writes NDJSON via `JsonFormat` with `schemas.enable=false`. S3 objects contain plain JSON records — identical to current Firehose output format. Databricks Auto Loader requires zero changes.

**Supersedes:** SA v2 supplement §3.4 recommended BACKWARD; data-engineer F-003 escalated to FULL because Silver `@dlt.expect_or_drop` silently drops all rows when a required field is removed under BACKWARD, making BACKWARD unsafe for this pipeline.

**Consequences:** All 5 job entrypoints require Avro schema registration at startup. Schema changes require a PR to `schemas/*.avsc` and a coordinated deploy. Breaking changes (type change, field rename) require a new topic name and Auto Loader checkpoint reset.

---

### ADR-CAPTURE-008: Kafka Connect S3 Sink (3 Connectors, JsonFormat Output)

**Decision:** S3 delivery for all three data streams (blocks, raw transactions, decoded transactions) is handled by Kafka Connect S3 Sink Connectors (3 connectors, not 2). Python job containers have no S3 write permission and do not call `boto3.put_object`. The S3 Sink Connector uses `format.class=io.confluent.connect.s3.format.json.JsonFormat` with `value.converter.schemas.enable=false` to produce NDJSON (not Avro, not Parquet) in S3.

**Rationale:** With the full Confluent Platform stack deployed, `cp-kafka-connect` is already running. The JVM cost that motivated the v1 `boto3` direct-write recommendation is a sunk cost. Kafka Connect S3 Sink provides at-least-once delivery, hourly file rotation, time-based partitioning, DLQ routing, and connector restart — all features that would need to be reimplemented in Python application code.

**Critical path constraint (data-engineer F-001):** The connector MUST be configured with:
- `topics.dir=raw` (not the default `topics/`)
- `partitioner.class=io.confluent.connect.storage.partitioner.TimeBasedPartitioner`
- `path.format='year'=YYYY/'month'=MM/'day'=dd/'hour'=HH`
- `timestamp.extractor=Record`

Without this exact configuration, the connector writes to `topics/<topic>/partition=P/` paths and Auto Loader reads 0 records.

**Three connectors, not two:** The `b_ethereum.eth_transactions` Bronze table reads `raw/mainnet-transactions-data/`. A third connector consuming `mainnet-transactions-data` is required in addition to the blocks and decoded transactions connectors. Each connector has a dedicated DLQ topic for S3 write failures: Connector 1 (`s3-sink-blocks`) → `s3-sink-blocks-dlq`; Connector 2 (`s3-sink-txs-data`) → `s3-sink-txs-data-dlq`; Connector 3 (`s3-sink-txs-decoded`) → `s3-sink-txs-decoded-dlq`. All DLQ topics: 1 partition, 7-day retention.

**`TransactionDecoded.avsc` must include `block_timestamp`:** The `timestamp.extractor=Record` uses the Kafka message timestamp. For the routing topics (`mainnet-transactions-data`), this is correct. For the decoded topic, `block_timestamp` is needed if `RecordField` extractor is used in future. The field must be included for correctness and forward compatibility.

**Consequences:** Python jobs 3 and 5 no longer manage S3 buffers or flush timers. Two new Kafka topics (`mainnet-blocks-data` and `mainnet-transactions-decoded`) are S3-delivery-only topics. A third connector configuration is required vs. what v2 data-architect planned.

---

### ADR-CAPTURE-009: Control Center SSH Tunnel Only; Replace with Kafka UI Before PROD

**Decision:** Confluent Control Center (`cp-enterprise-control-center`) has no `ports:` mapping in `docker-compose.yml`. The only access path is an SSH tunnel: `ssh -N -L 9021:control-center:9021 deploy@<vps-ip>`. Before PROD go-live, Control Center must be replaced by Kafka UI (Provectus, `provectuslabs/kafka-ui:latest`, MIT license).

**Rationale:** Control Center has no authentication by default. A `ports:` declaration would expose an unauthenticated management UI to the internet (Docker iptables bypass ufw/firewalld). The 30-day trial license makes it unsuitable for long-term production. Kafka UI provides equivalent topic browsing, consumer lag monitoring, and connector status at ~100 MB RAM footprint with no license concerns.

**Consequences:** Control Center can be used during initial DEV/HML validation (within the trial window). A TASKS.md item must cover the Kafka UI switch before PROD cutover.

---

## 6. Success Criteria

| # | Criterion | Validation |
|---|-----------|------------|
| SC-01 | VPS Docker stack starts cleanly: all 14 containers healthy | `docker compose ps` shows all services `running` or `healthy` |
| SC-02 | Schema Registry shows 5 Avro schemas registered | `curl http://schema-registry:8081/subjects` returns all 5 subject names |
| SC-03 | All 3 S3 Sink Connectors in `RUNNING` state | `curl http://connect:8083/connectors/s3-sink-blocks/status` → `RUNNING` (repeat for all 3) |
| SC-04 | Auto Loader in DEV receives NDJSON from S3 Sink Connector with correct hourly partitioning | Trigger `dlt_ethereum` DEV pipeline; verify `dev.b_ethereum.eth_mined_blocks` row count increases; verify Silver `valid_block_number` expectation passes (0 rows dropped) |
| SC-05 | All 3 Bronze tables ingest records from VPS-produced NDJSON | Same as SC-04, repeated for `eth_transactions` and `eth_txs_input_decoded` |
| SC-06 | S3 path matches current Firehose convention exactly | S3 object keys follow `raw/{stream}/year=Y/month=M/day=D/hour=H/` pattern |
| SC-07 | Redis SEMAPHORE mechanism works correctly for 6 Job 4 replicas | No API key assigned to more than 1 replica simultaneously; verified via Redis CLI `KEYS semaphore:*` |
| SC-08 | Fluent Bit delivers plain NDJSON to `raw/app_logs/` | S3 object at `raw/app_logs/year=.../` contains parseable JSON lines |
| SC-09 | `dm-app-logs` DLT pipeline processes logs after Bronze fix | DEV pipeline `dlt_app_logs` runs without error; `b_app_logs_data` row count increases |
| SC-10 | IAM Roles Anywhere credential refresh works | `aws_signing_helper credential-process` exits 0; credentials written to `/etc/dd-chain-capture/aws.env`; Connect container restarts and resumes S3 writes within 2 minutes |
| SC-11 | Control Center accessible via SSH tunnel only | Port 9021 not reachable from external IP; accessible via `ssh -L 9021:...` |
| SC-12 | AWS ECS Fargate tasks for Jobs 1-5 are stopped and decommissioned | ECS service desired count = 0; SQS queues drained; Kinesis streams confirmed empty for 24h |
| SC-13 | Kafka UI (Provectus) replaces Control Center before PROD go-live | `cp-enterprise-control-center` removed from compose; `provectuslabs/kafka-ui` running and accessible |
| SC-14 | Schema Registry compatibility set to FULL | `curl http://schema-registry:8081/config` returns `{"compatibility": "FULL"}` |

---

## 7. Dependencies

### 7.1 Hard Blocker — pipeline-restart-r1 Must Be ARCHIVED

`pipeline-restart-r1` is currently ACTIVE (phase: TASKS) in `repos/dd-chain-explorer/specs/releases/ACTIVE.md`. This release (`capture-decoupling-r5`) cannot begin implementation until `pipeline-restart-r1` is:
1. All tasks marked `[x]` DONE
2. CLOSURE.md written
3. Archived to `specs/_archive/releases/pipeline-restart-r1/`
4. `ACTIVE.md` updated to point to `capture-decoupling-r5` or `release: none`

**Reason:** The two releases have overlapping write surfaces (ECS task definitions, capture layer infrastructure). Concurrent implementation is not safe.

### 7.2 Dependency — dm-app-logs DLT Fix (dd-chain-explorer)

The Bronze UDF fix in `dlt_app_logs` (`cloudFiles.format=binaryFile` → `cloudFiles.format=json`, removal of `_extract_cw_log_events`) must be deployed to DEV before the VPS capture layer cutover in DEV. Without this fix, `b_app_logs_data` processes 0 records from Fluent Bit output.

**Ordering:** This fix can be developed in parallel with VPS infrastructure setup but must be deployed before the DEV cutover gate (SC-09).

### 7.3 Dependency — OpenSSL CA Setup (Operator)

The self-signed CA (`ca.key`, `ca.crt`) must be created on the operator's machine before VPS certificate issuance. The VPS certificate (`vps.crt`, `vps.key`) and IAM Roles Anywhere Trust Anchor must be configured in AWS before PROD deployment. This is a manual operator step with no automation shortcut.

---

## 8. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| S3 Sink Connector path misconfiguration (auto loader reads 0 records) | HIGH | HIGH | Validate in DEV with `topics.dir=raw` + TimeBasedPartitioner before promoting to HML. SC-04/SC-05 are explicit gates. |
| Control Center trial expiry before PROD go-live | HIGH | MEDIUM | SC-13 mandates Kafka UI replacement. TASKS.md item explicitly assigned before PROD cutover. |
| Kafka Connect credential refresh window — S3 writes pause | MEDIUM | MEDIUM | Cron restarts Connect every 50 min (10 min before STS expiry). Investigate `credential_process` inside Connect container as a long-term fix (TASKS.md item). |
| CA key compromise on operator machine | LOW | CRITICAL | CA key stored encrypted (LUKS/macOS Keychain). 90-day certificate validity limits blast radius. Revocation via Trust Anchor deletion if needed. |
| VPS RAM pressure (8 GB minimum) | MEDIUM | MEDIUM | Monitor memory. Control Center can be omitted in DEV/HML to save 1.8 GB. Upgrade to 16 GB VPS before PROD if needed. |
| dm-app-logs DLT fix introduces regression in Gold API key analytics | LOW | HIGH | Run DEV pipeline after Bronze fix; validate Silver `logs_streaming` and Gold `etherscan_consumption` row counts before VPS cutover. |
| Schema FULL compatibility blocks a needed field removal | LOW | LOW | FULL compatibility is the right tradeoff. Planned field removals require schema versioning (new topic name) — process is documented, not blocked. |
| Single Kafka broker failure causes capture downtime | MEDIUM | MEDIUM | Ethereum RPC is re-tailable from chain head. Expected recovery time < 5 minutes (container restart). No data loss beyond the gap window. |
| `TransactionDecoded.avsc` missing `block_timestamp` | HIGH | HIGH | Schema design constraint documented. backend-engineer must include field. Validated via schema inspection before first production deployment. |

---

## 9. Memory Files Affected at CLOSURE

At CLOSURE phase of this release, the following memory HTML files must be updated to reflect the new architecture. Memory describes the current state after the release, not a changelog.

| File | Update required |
|------|----------------|
| `specs/memory/architecture.html` | Replace capture layer section: ECS Fargate → Hostinger VPS + Confluent Platform. Replace SQS/Kinesis/Firehose with Kafka topics/connectors. Replace DynamoDB hot entities with Redis. Add ADR-CAPTURE-001 through ADR-CAPTURE-009. Remove ADR-001 (now superseded by ADR-CAPTURE-006 for the capture layer). Update environment topology table (VPS for all envs). Update PRD Deploy Order. |
| `specs/memory/tech-stack.html` | Add: Confluent Platform 7.6.x (Kafka KRaft, Schema Registry, Kafka Connect, Control Center/Kafka UI). Add: Redis 7-alpine. Add: Fluent Bit 3.0. Add: IAM Roles Anywhere. Add: Avro/fastavro, confluent-kafka-python. Remove: Kinesis Data Streams, Kinesis Firehose, SQS (for capture layer). Note: boto3 remains for other uses (Lambda, etc.). |
| `specs/memory/product/index.html` | Catalog order and feature descriptions unchanged. If `dd-chain-capture` is treated as a new product context, a new context should be created. Within `dd-chain-explorer` memory, the capture layer description changes from ECS to VPS. |

---
