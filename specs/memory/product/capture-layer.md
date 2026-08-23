---
slug: capture-layer
title: Capture Integration
category: product
tldr: Capture lives in the external dd-chain-capture project on a VPS; this repository only consumes the raw JSON it delivers to the S3 raw bucket.
summary: Describes how Ethereum data enters the platform after capture retirement. Ingestion of blocks, transactions and calldata is owned by the external dd-chain-capture project running on a VPS, which writes Kafka-Connect JSON into the S3 raw bucket under mainnet prefixes with year/month/day partitions, plus Fluent-Bit NDJSON application logs. The bucket is the only contract — no queue, stream, shared library or network path. Field-name compatibility with the DLT Auto Loader schemas is not yet validated, and the bucket has held no data since 2026-05-23.
tags:
  - capture
  - integration
  - s3
  - ethereum
  - boundary
last_updated: "2026-08-23"
release_origin: v0.5.0
---

## Propósito

Data capture is **not** a feature of this repository. Ethereum block, transaction and
calldata ingestion is owned by a separate project, **dd-chain-capture**, which runs on a
VPS outside this account's compute. This atom documents the seam between the two
projects, because everything downstream depends on it.

The seam is a single S3 bucket. dd-chain-capture writes raw JSON objects into
`dm-chain-explorer-raw-data`; this platform's Databricks Auto Loader reads them. There is
no queue, no stream, no shared database, no shared library and no network path between
the two projects. Either side can be redeployed, rewritten or stopped without touching
the other, as long as the object contract holds.

Nothing in this repository captures, polls or decodes chain data. The five ECS Fargate
producer jobs, the Kinesis stream, the Firehose delivery streams and the SQS queues that
used to fill this role were destroyed in AWS, and their Terraform stacks, modules,
container images and Python code were deleted — git history is their only archive.
Reintroducing them here is forbidden by ADR-007, not merely out of scope.

## Fluxo de uso

1. dd-chain-capture ingests Ethereum mainnet data on its VPS and serialises it as
   Kafka-Connect-style JSON.
2. It writes objects to `s3://dm-chain-explorer-raw-data/raw/mainnet-blocks-data/`,
   `raw/mainnet-transactions-data/` and `raw/mainnet-transactions-decoded/`, partitioned
   `year=YYYY/month=MM/day=DD/…`.
3. Its application logs are shipped by Fluent-Bit as NDJSON to `raw/app_logs/`.
4. The Databricks Auto Loader in [[medallion-pipelines]] discovers new objects
   incrementally under those prefixes (JSON format, `partitionColumns=""`) and lands them
   in the bronze layer.
5. Downstream silver and gold transformations, dashboards and exports proceed as
   [[serving-layer]] describes.

## Trigger típico

Consulted whenever a change touches the raw prefixes, the Auto Loader path configuration,
the bucket's policy or lifecycle rules, or whenever someone asks where blockchain data
comes from.

## Diferencial

Separating capture from processing removes the platform's largest operational and cost
liability: the always-on streaming fleet. It also decouples release cycles — the capture
project can change its runtime, its provider or its language without a single change
here, and this platform can be idle at near-zero cost while still being ready to process
whatever arrives. The price of that decoupling is that the contract is implicit in the
object layout, so it must be documented and verified rather than enforced by a schema
registry.

## Estado runtime tocado

- S3 `dm-chain-explorer-raw-data` — `raw/mainnet-blocks-data/`,
  `raw/mainnet-transactions-data/`, `raw/mainnet-transactions-decoded/`, `raw/app_logs/`
  (written by dd-chain-capture; read by Databricks)
- Databricks Auto Loader checkpoints under `s3://dm-chain-explorer-lakehouse/checkpoints/`
- SSM `/web3-api-keys/infura/*` and `/web3-api-keys/alchemy/*` — the shared secret plane
  dd-chain-capture reads; this repository does not consume these parameters
- Terraform state key `capture/ecr` in this repository's state bucket holds
  dd-chain-capture's ECR repositories, IAM Roles Anywhere trust anchor and KMS key —
  cross-project state with no source code here

## Dependências

- **dd-chain-capture** (external project, VPS) — the sole producer of raw chain data
- **[[aws-resources]]** — the raw bucket, its lifecycle rules and the IAM the producer
  assumes
- **Triggers → [[medallion-pipelines]]** — the downstream consumer via Auto Loader

**Parked until delivery.** The consuming half is deployed, validated and deliberately
idle: DLT pipelines deployed and IDLE, trigger jobs paused, the contracts-ingestion
schedule disabled, the raw bucket empty since 2026-05-23. This is the intended steady
state while dd-chain-capture builds up to its first delivery, not a degraded one — the
restart is un-pausing the trigger jobs. The posture, what it forbids, and the criteria
that end it are ADR-007 in [[architecture]].

**Open verification.** Field-name compatibility between the JSON dd-chain-capture
delivers and the schemas the DLT bronze tables expect has **not** been validated. The
path and format contract is compatible; the field-level contract is unproven. No delivery
has been processed end to end, so this is the first-ingestion risk, and validating it is
a sunset criterion of ADR-007.

**No residue.** Every capture-era resource of this account is gone — the IAM grants, the
ECS shells, the unmanaged VPC and its leaked security groups were destroyed and their
Terraform deleted. Nothing here points back across the boundary.
