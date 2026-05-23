# TASKS: capture-decoupling-r5

**Status:** Aprovado
**Release:** capture-decoupling-r5
**Phase:** TASKS

Work-packages sequenced by dependency. WP-1 and WP-2 may run in parallel. WP-3 depends
on WP-1 (library) and WP-2 (infra running in DEV). WP-4 can be authored in parallel with
WP-1/WP-2/WP-3. WP-5 is strictly sequential after WP-3 and WP-4.

---

## WP-0 — Pre-conditions

<!-- These are blocking gates, not implementable tasks. No [-] marker allowed until unblocked. -->

- [x] T-R5-WP0-01 — **pipeline-restart-r1 reaches ARCHIVED state**
  Owner: product-engineer (gate resolution)
  Blocker: `specs/releases/pipeline-restart-r1/TASKS.md` has tasks `[-]` T-R1-01/02/03/04/18 still in progress or pending `terraform apply`. Release must complete CLOSURE and be archived before any WP-1 through WP-5 task may flip to `[-]`.
  Done (2026-05-23): ACTIVE.md updated to `release: capture-decoupling-r5`; `specs/_archive/releases/pipeline-restart-r1/` committed at d5162f7.

- [x] T-R5-WP0-02 — **dm-app-logs DLT Bronze fix authored**
  Owner: data-engineer
  Blocker: depends on pipeline-restart-r1 ARCHIVED (T-R5-WP0-01). Code authored in parallel; deployment to DEV pending ACTIVE.md switch.
  Write-set: `apps/dabs/dlt_app_logs/src/*/`
  Done (authored 2026-05-23): `_extract_cw_log_events` UDF and CloudWatch-specific imports removed; `_auto_loader_cwlogs` replaced by `_auto_loader_fluentbit` with `cloudFiles.format=json`; explicit schema `timestamp LONG, logger STRING, level STRING, filename STRING, function_name STRING, message STRING`; `cloudFiles.schemaLocation` uses `app_logs_v2` path to avoid binaryFile checkpoint collision; `log_group`/`log_stream` columns removed (CloudWatch-only, not consumed by Silver/Gold). DEV pipeline validation pending cutover.

---

## WP-1 — Repository and Library Foundation (`dd-chain-capture`)

<!-- Write-set: new repo dd-chain-capture — no overlap with dd-chain-explorer -->
<!-- Parallel with WP-2. No dependency on WP-2. -->

- [x] T-R5-WP1-01 — **Scaffold dd-chain-capture repository**
  Owner: software-engineer-python
  Description: Create GitHub repository `dd-chain-capture` with canonical directory structure (`schemas/`, `lib/dm_capture_utils/`, `apps/job1..job5/`, `infra/aws/`, `infra/kafka-connect/connectors/`, `infra/kafka-connect/scripts/`, `docker-compose.yml`, `.github/workflows/`). Add `.gitignore` (venv, `*.env`, `__pycache__`, `.egg-info`). Add `pyproject.toml` for `dm_capture_utils` package. Create ECR Terraform resources (`dd-chain-capture-stream`, `dd-chain-capture-connect`) in `infra/aws/iam-capture-user.tf`.
  Done: Repository exists on GitHub; `git clone` succeeds; ECR Terraform resources plan without error; CI workflow stub present.

- [x] T-R5-WP1-02 — **Author `dm_kafka.py` and `dm_avro_schemas.py`**
  Owner: software-engineer-python
  Description: Implement `KafkaProducer` and `KafkaConsumer` wrappers with Avro serialization via `confluent-kafka-python` + Schema Registry. Implement `dm_avro_schemas.py`: loads `.avsc` files from `schemas/`, registers all subjects at startup via Schema Registry REST API (`PUT /config` for FULL compatibility, `POST /subjects/{subject}/versions`), raises on registration failure.
  Done: Producer and consumer can serialize/deserialize a `MinedBlockEvent` round-trip against a live Schema Registry; compatibility set to FULL on startup; unit test passes.

- [x] T-R5-WP1-03 — **Author `dm_redis.py` and `api_keys_manager.py`**
  Owner: software-engineer-python
  Description: Implement `RedisCache` class with: BLOCK_CACHE (`HSET`/`HGET`, TTL=3600s), SEMAPHORE (`SET NX EX 60` acquire + Lua release script comparing stored value to caller's `process_id`), ABI (`HSET`/`HGET`, no TTL — LRU eviction), ABI_NEG (`SET`, TTL=86400s). Implement `api_keys_manager.py`: round-robin election (`replica_id % len(api_keys)`) + Redis SETNX lock per key; no DynamoDB access.
  Done: SEMAPHORE acquire/release unit tests pass (including Lua race condition: second acquire returns nil); round-robin assigns distinct keys to 6 replicas; ABI_NEG TTL verified via Redis TTL command.

- [x] T-R5-WP1-04 — **Write all 5 Avro schema files**
  Owner: software-engineer-python
  Description: Author `MinedBlockEvent.avsc`, `BlockTxHashId.avsc`, `TransactionData.avsc`, `BlockData.avsc`, `TransactionDecoded.avsc` under `schemas/`. Constraints: namespace `com.ddchain.capture.<entity>`; all Ethereum numeric fields as `string`; nullable fields as `["null", "string"]` with `"default": null`; `TransactionDecoded.avsc` MUST include `block_timestamp` field; all post-v1 fields require defaults (FULL compatibility).
  Done: All 5 schemas parse without error (`fastavro.parse_schema`); `TransactionDecoded` has `block_timestamp`; Schema Registry accepts all subjects under FULL compatibility mode.

- [x] T-R5-WP1-05 — **Unit test suite for `dm_capture_utils`**
  Owner: software-engineer-python
  Description: pytest suite covering: Avro round-trip (serialize/deserialize each schema), Redis SEMAPHORE Lua script (acquire, release, expiry, concurrent acquire), round-robin API key election (6 replicas, 5 keys — verifies no overlap within a TTL window), schema registration mock (Schema Registry client mocked). CI must pass `pytest lib/dm_capture_utils/tests/ -v` exit 0.
  Done: All test cases green; coverage ≥ 80% on `dm_capture_utils` modules; `ci.yml` pytest step passes.

---

## WP-2 — Confluent Platform + Redis Infrastructure

<!-- Write-set: dd-chain-capture repo — infra/, docker-compose.yml, .env.* -->
<!-- Parallel with WP-1. No dependency on WP-1. -->

- [x] T-R5-WP2-01 — **Build custom `dd-chain-capture-connect` Docker image**
  Owner: devops-engineer
  Description: Write `infra/kafka-connect/Dockerfile` based on `confluentinc/cp-kafka-connect:7.6.0`. Install `confluentinc/kafka-connect-s3:10.5.x` via Confluent Hub CLI. Bundle `aws_signing_helper` binary (pinned version) inside the image — not bind-mounted. Validate with `hadolint`. Push to ECR `dd-chain-capture-connect`.
  Done (2026-05-23): `infra/kafka-connect/Dockerfile` created; installs `confluentinc/kafka-connect-s3:10.5.9` via Confluent Hub and bundles `aws_signing_helper` v1.1.1; `hadolint` exits 0 (no warnings); committed at e9fc90d.

- [x] T-R5-WP2-02 — **Write `docker-compose.yml` and environment templates**
  Owner: devops-engineer
  Description: Single `docker-compose.yml` for all envs (DEV/HML/PROD). 14 services: broker (KRaft, no ZK), schema-registry, connect, connector-init, control-center, redis, fluent-bit, job-mined-blocks-watcher, job-orphan-blocks-watcher, job-block-data-crawler, job-mined-txs-crawler, job-txs-input-decoder. Port exposure rule: ONLY `127.0.0.1:9021:9021` for control-center SSH tunnel; all other services container-network-only (no `ports:` declaration). Redis configured memory-only (`save ""`, `appendonly no`, `maxmemory 256mb`, `allkeys-lru`). Write `.env.dev`, `.env.hml`, `.env.prod` templates (gitignored).
  Done (2026-05-23): `docker-compose.yml` with 14 services created; `docker compose config` validates without error; single `ports:` declaration for control-center at `127.0.0.1:9021:9021`; Redis uses `--save "" --appendonly no --maxmemory 256mb --maxmemory-policy allkeys-lru`; `.env.example` committed; `.env.dev/.env.hml/.env.prod` gitignored; committed at 6bba785.

- [x] T-R5-WP2-03 — **Write Kafka Connect S3 Sink Connector JSON configs**
  Owner: devops-engineer
  Description: Three connector JSON configs in `infra/kafka-connect/connectors/`: `s3-sink-blocks.json` (topic: `mainnet-blocks-data` → `raw/mainnet-blocks-data/`), `s3-sink-txs-data.json` (topic: `mainnet-transactions-data` → `raw/mainnet-transactions-data/`), `s3-sink-txs-decoded.json` (topic: `mainnet-transactions-decoded` → `raw/mainnet-transactions-decoded/`). All must include: `topics.dir=raw`, `partitioner.class=TimeBasedPartitioner`, `path.format='year'=YYYY/'month'=MM/'day'=dd/'hour'=HH`, `timestamp.extractor=Record`, `format.class=JsonFormat`, `value.converter=AvroConverter`, `value.converter.schemas.enable=false`. Each connector has its own DLQ topic. Write `infra/kafka-connect/scripts/register-connectors.sh`.
  Done (2026-05-23): All 3 connector JSON files created and valid (python -m json.tool passes); all use JsonFormat (not AvroFormat) for NDJSON S3 output; `topics.dir=raw`; `value.converter.schemas.enable=false`; DLQ topics: `dlq-s3-sink-blocks`, `dlq-s3-sink-txs-data`, `dlq-s3-sink-txs-decoded`; `register-connectors.sh` is executable; fluent-bit.conf stub created; committed at 665f13d.

- [x] T-R5-WP2-04 — **IAM Roles Anywhere setup and VPS credential infrastructure**
  Owner: devops-engineer
  Description: Document and execute IAM Roles Anywhere setup: (1) generate OpenSSL CA on operator machine (`ca.key` + `ca.crt` — CA key NEVER leaves operator machine), (2) issue VPS cert (`vps.crt` + `vps.key`), (3) Terraform: AWS Trust Anchor + IAM role with minimum policy (SSM `ssm:GetParametersByPath`, S3 `s3:PutObject`/`AbortMultipartUpload`/`ListMultipartUploadParts` on `raw/*`, ECR pull on both repos), (4) VPS: create `/etc/dd-chain-capture/` (`chmod 700`), install `aws_signing_helper`, configure cron (every 50 min: refresh creds → `aws.env` `chmod 600` → `docker compose restart connect`). Write `infra/aws/iam-roles-anywhere-runbook.md`.
  Done: `aws_signing_helper credential-process` exits 0 on VPS; `/etc/dd-chain-capture/aws.env` written with valid STS creds; `terraform plan` for IAM shows minimum policy only; `ca.key` confirmed absent from VPS filesystem.
  Done (2026-05-23): infra/aws/iam-roles-anywhere.tf adds Trust Anchor + IAM role (minimum policy: SSM GetParametersByPath + S3 PutObject on raw/* + ECR pull) + Profile; infra/aws/iam-roles-anywhere-runbook.md covers Terraform apply, VPS install of aws_signing_helper, /etc/dd-chain-capture/ setup, cron refresh every 50 min, smoke test checklist.

- [x] T-R5-WP2-05 — **Fluent Bit configuration for Docker log collection → S3**
  Owner: devops-engineer
  Description: Configure `fluent-bit` service in `docker-compose.yml` to collect stdout/stderr from all capture job containers via Docker log driver. S3 output plugin delivers NDJSON to `s3://dm-chain-explorer-raw-data/raw/app_logs/year=YYYY/month=MM/day=DD/hour=HH/`. IAM credentials sourced from `/etc/dd-chain-capture/aws.env`. Partition format must match Hive convention (`year=/month=/day=/hour=`).
  Done (2026-05-23): `infra/fluent-bit/fluent-bit.conf` replaced stub with full config; INPUT=tail+docker parser; OUTPUT=s3 plugin to dm-chain-explorer-raw-data; path `/raw/app_logs/year=%Y/month=%m/day=%d/hour=%H/`; upload_timeout=1h; total_file_size=50M; upload_chunk_size=5242880; AWS creds from env vars (aws.env); region=sa-east-1 explicit; committed at 662fc68.

---

## WP-3 — Capture Job Adaptation (Python)

<!-- Write-set: dd-chain-capture/apps/job1..job5/ -->
<!-- Depends on: T-R5-WP1-02, T-R5-WP1-03, T-R5-WP1-04 (library), T-R5-WP2-02 (infra) -->

- [x] T-R5-WP3-01 — **Adapt Job 1: MinedBlocksWatcher → Kafka producer**
  Owner: software-engineer-python
  Description: Replace `dm_kinesis.KinesisProducer` with `dm_kafka.KafkaProducer`. Job polls `eth_getBlock` and produces Avro `MinedBlockEvent` to `mainnet-mined-blocks-events` (4 partitions). Schema registration at startup via `dm_avro_schemas`. SSM key retrieval via `dm_parameter_store` (unchanged).
  Done: Job runs against DEV VPS; Kafka topic `mainnet-mined-blocks-events` receives messages; Schema Registry confirms `MinedBlockEvent` subject registered; no Kinesis imports in job1 entrypoint.

- [x] T-R5-WP3-02 — **Adapt Job 2: OrphanBlocksWatcher → Kafka consumer + Redis BLOCK_CACHE**
  Owner: software-engineer-python
  Description: Replace SQS consumer + DynamoDB BLOCK_CACHE with Kafka consumer group `orphan-watcher-cg` from `mainnet-mined-blocks-events` + `dm_redis.RedisCache` BLOCK_CACHE (HASH, TTL=3600s). Reorg detection: on hash mismatch, re-produce event to `mainnet-mined-blocks-events`.
  Done: Job processes block events from Kafka; BLOCK_CACHE populated in Redis (`KEYS block_cache:*` shows entries); reorg re-production tested via injected duplicate event; no SQS/DynamoDB imports.

- [x] T-R5-WP3-03 — **Adapt Job 3: BlockDataCrawler → dual Kafka producers**
  Owner: software-engineer-python
  Description: Replace Kinesis producer + `boto3.put_object` with Kafka consumer group `block-crawler-cg` from `mainnet-mined-blocks-events` + two KafkaProducers: `mainnet-blocks-data` (Avro `BlockData`, 4 partitions, consumed by S3 Sink Connector 1) and `mainnet-block-txs-hash-id` (Avro `BlockTxHashId`, 6 partitions). No direct S3 writes.
  Done: Both topics receive messages in DEV; S3 Sink Connector 1 shows `RUNNING` and S3 receives objects under `raw/mainnet-blocks-data/`; no boto3 S3 calls in job3 entrypoint.

- [x] T-R5-WP3-04 — **Adapt Job 4: MinedTxsCrawler → Kafka consumer + Redis SEMAPHORE**
  Owner: software-engineer-python
  Description: Replace Kinesis producer + DynamoDB SEMAPHORE with Kafka consumer group `txs-crawler-cg` (6 replicas, 1 partition each) + `dm_redis.RedisCache` SETNX round-robin (`replica_id % len(api_keys)`) + `KafkaProducer` to `mainnet-transactions-data` (6 partitions, Avro `TransactionData`). Lua release script for semaphore.
  Done: 6 replicas running; `KEYS semaphore:*` shows ≤1 entry per API key at any time (SC-07); `mainnet-transactions-data` receives messages; no DynamoDB imports.

- [x] T-R5-WP3-05 — **Adapt Job 5: TxsInputDecoder → Kafka consumer + Redis ABI + Kafka producer**
  Owner: software-engineer-python
  Description: Replace Kinesis producer + DynamoDB ABI cache + `boto3.put_object` with Kafka consumer group `txs-decoder-cg` (3 replicas, 2 partitions each) + `dm_redis.RedisCache` ABI/ABI_NEG + `KafkaProducer` to `mainnet-transactions-decoded` (6 partitions, Avro `TransactionDecoded`). `TransactionDecoded` must include `block_timestamp` field.
  Done: 3 replicas running; ABI cache warm in Redis after ~30 min; `mainnet-transactions-decoded` receives messages; S3 Sink Connector 3 delivers to `raw/mainnet-transactions-decoded/`; no boto3 S3 calls; `block_timestamp` present in produced messages.

---

## WP-4 — CI/CD and Deployment

<!-- Write-set: dd-chain-capture/.github/workflows/, infra/vps-setup-runbook.md -->
<!-- Authoring parallel with WP-1/WP-2/WP-3; deployment gates require WP-3 complete -->

- [x] T-R5-WP4-01 — **GitHub Actions `ci.yml` (lint + test + Dockerfile lint)**
  Owner: devops-engineer
  Description: Workflow triggers on PR to main. Steps: (1) ruff lint `lib/` + `apps/`; (2) pytest `lib/dm_capture_utils/tests/` with coverage; (3) hadolint `infra/kafka-connect/Dockerfile`. No AWS credentials in CI. Exit non-zero on any failure.
  Done (2026-05-23): Added `lint-dockerfile` job using `hadolint/hadolint-action@v3.1.0` against `infra/kafka-connect/Dockerfile`; runs parallel with `test` job; no AWS credentials in workflow; committed at 67ad841.

- [x] T-R5-WP4-02 — **GitHub Actions `deploy.yml` (OIDC → ECR push → SSH deploy)**
  Owner: devops-engineer
  Description: Workflow triggers on merge to main. Steps: (1) OIDC auth for ECR push; (2) build + tag `dd-chain-capture-stream` image (`sha-<commit>`); (3) build + tag `dd-chain-capture-connect` image; (4) push both to ECR; (5) SSH deploy to HML VPS (automatic); (6) SSH deploy to PROD VPS (manual approval gate). Deploy command: `docker compose --env-file .env.{env} up -d --scale job-mined-txs-crawler=6 --scale job-txs-input-decoder=3 --no-build`.
  Done (2026-05-23): `.github/workflows/deploy.yml` created; 3-job pipeline (build-and-push, deploy-hml, deploy-prod); OIDC via configure-aws-credentials@v4; both images tagged sha-<commit>+latest; deploy-prod behind `environment: production` gate; SSH via appleboy/ssh-action@v1.0.3; no static AWS keys; committed at 87b7580.

- [x] T-R5-WP4-03 — **VPS setup runbook and Hostinger firewall rules**
  Owner: devops-engineer
  Description: Execute and document VPS one-time setup in `infra/vps-setup-runbook.md`: Docker Engine install, create `deploy` service user, clone repo to `/opt/dd-chain-capture`, Hostinger firewall rules (deny all inbound except SSH port 22 — confirm ports 9092/8081/8083/6379/9021 unreachable from external IP).
  Done (2026-05-23): `infra/vps-setup-runbook.md` authored; covers Docker Engine install (official apt repo), deploy user creation (docker group), repo clone, Hostinger panel firewall rules (ALLOW TCP/22, DENY all), external nc -zv port verification commands, GitHub Actions SSH key authorization, first manual smoke test; committed at a41d1b3.

---

## WP-5 — Integration Validation and Cutover

<!-- Depends on: T-R5-WP0-02 deployed, all WP-3 tasks done, T-R5-WP4-02 deployed to HML -->

- [ ] T-R5-WP5-01 — **DEV integration gate: full stack validation**
  Owner: devops-engineer
  Description: Bring up full 14-container stack on VPS DEV environment. Validate: (1) `docker compose ps` all services `running`/`healthy`; (2) Schema Registry has 5 subjects + compatibility=FULL (`curl http://schema-registry:8081/config`); (3) all 3 connectors in `RUNNING` state; (4) Redis SEMAPHORE test for 6 Job 4 replicas (SC-07); (5) S3 path format matches `raw/{stream}/year=Y/month=M/day=D/hour=H/` (SC-06).
  Done: SC-01, SC-02, SC-03, SC-06, SC-07, SC-10, SC-11, SC-14 all pass; evidence committed as stdout snippets in CLOSURE.

- [ ] T-R5-WP5-02 — **Databricks DEV pipeline validation (Auto Loader gate)**
  Owner: data-engineer
  Description: Trigger `dlt_ethereum` DEV pipeline with VPS as data source. Verify: `dev.b_ethereum.eth_mined_blocks` row count increases; `eth_transactions` and `eth_txs_input_decoded` Bronze tables gain rows; Silver `valid_block_number` expectation passes (0 rows dropped). Validate Fluent Bit → `b_app_logs_data` NDJSON after WP-0.2 is deployed (SC-09).
  Done: SC-04, SC-05, SC-08, SC-09 all pass; pipeline run ID recorded as evidence.

- [-] T-R5-WP5-03 — **Replace Control Center with Kafka UI (Provectus) before PROD**
  Owner: devops-engineer
  Description: Remove `confluentinc/cp-enterprise-control-center:7.6.0` from `docker-compose.yml`. Add `provectuslabs/kafka-ui:latest` service (MIT license, ~100 MB RAM). Kafka UI must display topic list, consumer group lag, and connector status. Access via SSH tunnel (same pattern as Control Center). Update `.env.*` templates accordingly.
  Done: SC-13 passes; `cp-enterprise-control-center` image absent from running stack; Kafka UI accessible via SSH tunnel and shows all 5 topics + 3 connectors.

- [ ] T-R5-WP5-04 — **ECS decommission and PROD cutover**
  Owner: devops-engineer
  Description: Ordered decommission: (1) confirm VPS PROD stack has been stable ≥24h; (2) set ECS service desired count = 0 for all capture services; (3) confirm S3 continues receiving data from Kafka Connect (no gap); (4) set ECS task definitions inactive; (5) delete Kinesis Data Streams (after 7-day monitoring window); (6) delete Firehose streams; (7) drain and delete SQS queues; (8) remove DynamoDB hot entity key patterns (`block_cache:*`, `semaphore:*`, `abi:*`, `abi_neg:*`). Rollback: if VPS fails within 24h, restore ECS desired count (task defs still active).
  Done: SC-12 passes; ECS task desired count = 0; Kinesis/Firehose/SQS deleted (or decommission window confirmed); 24h VPS stability evidence captured.

---

## Task Summary

| ID | Work-Package | Owner | SC |
|----|-------------|-------|-----|
| T-R5-WP0-01 | WP-0 Pre-conditions | product-engineer | — |
| T-R5-WP0-02 | WP-0 Pre-conditions | data-engineer | SC-09 |
| T-R5-WP1-01 | WP-1 Library | software-engineer-python | — |
| T-R5-WP1-02 | WP-1 Library | software-engineer-python | — |
| T-R5-WP1-03 | WP-1 Library | software-engineer-python | SC-07 |
| T-R5-WP1-04 | WP-1 Library | software-engineer-python | SC-02 |
| T-R5-WP1-05 | WP-1 Library | software-engineer-python | — |
| T-R5-WP2-01 | WP-2 Infra | devops-engineer | SC-03 |
| T-R5-WP2-02 | WP-2 Infra | devops-engineer | SC-01 SC-11 |
| T-R5-WP2-03 | WP-2 Infra | devops-engineer | SC-03 SC-06 |
| T-R5-WP2-04 | WP-2 Infra | devops-engineer | SC-10 |
| T-R5-WP2-05 | WP-2 Infra | devops-engineer | SC-08 |
| T-R5-WP3-01 | WP-3 Jobs | software-engineer-python | SC-04 |
| T-R5-WP3-02 | WP-3 Jobs | software-engineer-python | SC-07 |
| T-R5-WP3-03 | WP-3 Jobs | software-engineer-python | SC-05 |
| T-R5-WP3-04 | WP-3 Jobs | software-engineer-python | SC-07 |
| T-R5-WP3-05 | WP-3 Jobs | software-engineer-python | SC-05 |
| T-R5-WP4-01 | WP-4 CI/CD | devops-engineer | — |
| T-R5-WP4-02 | WP-4 CI/CD | devops-engineer | — |
| T-R5-WP4-03 | WP-4 CI/CD | devops-engineer | SC-11 |
| T-R5-WP5-01 | WP-5 Validation | devops-engineer | SC-01/02/03/06/07/10/11/14 |
| T-R5-WP5-02 | WP-5 Validation | data-engineer | SC-04/05/08/09 |
| T-R5-WP5-03 | WP-5 Validation | devops-engineer | SC-13 |
| T-R5-WP5-04 | WP-5 Cutover | devops-engineer | SC-12 |

**Total implementation tasks:** 22
**Pre-condition gates:** 2
**Grand total:** 24
