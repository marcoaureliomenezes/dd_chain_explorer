# Integration Test Rules — HML CI/CD Gate

Mandatory checks that must pass before a release branch is created.

---

## 1. onchain-stream-txs Pipeline

**Script**: `scripts/hml_integration_test.sh`
**Workflow**: `deploy_streaming_apps.yml` → job `hml-integration-test`

| # | Check | Resource | Condition |
|---|---|---|---|
| 1 | SQS messages sent | `mainnet-mined-blocks-events-hml` | CloudWatch `NumberOfMessagesSent` > 0 (5 min window) |
| 2 | SQS messages sent | `mainnet-block-txs-hash-id-hml` | CloudWatch `NumberOfMessagesSent` > 0 (5 min window) |
| 3 | Kinesis incoming | `mainnet-blocks-data-hml` | CloudWatch `IncomingRecords` > 0 (5 min window) |
| 4 | Kinesis incoming | `mainnet-transactions-data-hml` | CloudWatch `IncomingRecords` > 0 (5 min window) |
| 5 | Kinesis incoming | `mainnet-transactions-decoded-hml` | CloudWatch `IncomingRecords` > 0 (5 min window) |
| 6 | DynamoDB items | `dm-chain-explorer-hml` | Scan count ≥ 1 |
| 7 | Firehose status | `firehose-mainnet-blocks-data-hml` | Status = ACTIVE |
| 8 | Firehose status | `firehose-mainnet-transactions-data-hml` | Status = ACTIVE |
| 9 | Firehose status | `firehose-mainnet-transactions-decoded-hml` | Status = ACTIVE |
| 10 | S3 delivery | `raw/mainnet-blocks-data/` | ≥ 1 `.gz` file in last 10 min |
| 11 | S3 delivery | `raw/mainnet-transactions-data/` | ≥ 1 `.gz` file in last 10 min |
| 12 | S3 delivery | `raw/mainnet-transactions-decoded/` | ≥ 1 `.gz` file in last 10 min |

**Pass criteria**: all 12 checks PASS. Any FAIL → block release.

---

## 2. DLT Pipeline (Databricks)

**Script**: `scripts/hml_dlt_integration_test.sh`
**Workflow**: `deploy_databricks.yml` → job `hml-dlt-integration-test`

### Mandatory Gold MVs (row_count > 0)

| # | Pipeline | Gold MV | Source |
|---|---|---|---|
| 1 | dm-ethereum | `s_apps.popular_contracts_ranking` | `transactions_fast` (1h window) |
| 2 | dm-ethereum | `s_apps.peer_to_peer_txs` | `transactions_ethereum` (EOA→EOA filter) |
| 3 | dm-ethereum | `s_apps.ethereum_gas_consume` | `transactions_ethereum` (gas classification) |
| 4 | dm-ethereum | `g_network.network_metrics_hourly` | `blocks_fast` + `transactions_fast` |
| 5 | dm-app-logs | `g_api_keys.etherscan_consumption` | `logs_streaming` + `logs_batch` |
| 6 | dm-app-logs | `g_api_keys.web3_keys_consumption` | `logs_streaming` + `logs_batch` |

### Skipped (TODO — batch dependency)

| Gold MV | Reason |
|---|---|
| `s_apps.transactions_lambda` | Depends on `b_ethereum.popular_contracts_txs` (batch pipeline). See TODO below. |

**Pass criteria**: all 6 mandatory Gold MVs have row_count > 0. Any FAIL → block release.

---

## 3. TODO — Batch Popular Contracts Pipeline

**Not yet tested.** The full batch flow requires:

1. DLT Gold MV `popular_contracts_ranking` → top 100 contracts
2. Periodic workflow exports ranking to DynamoDB (via Lambda)
3. Another Lambda reads DynamoDB contracts → fetches txs from Etherscan API
4. Lambda writes batch txs to S3 (raw bucket)
5. DLT reads from S3 → `b_ethereum.popular_contracts_txs` (Bronze)
6. Gold MV `transactions_lambda` JOINs streaming + batch data

**Complexity**: requires Lambda functions, Etherscan API keys, DynamoDB orchestration, and careful mapping of the data flow before building a reliable integration test.

---

## Execution Order in CI/CD

### `deploy_streaming_apps.yml`
```
build-rc → hml-provision → hml-deploy → hml-integration-test → hml-teardown → create-release-branch
```

### `deploy_databricks.yml`
```
branch-guard → check-infra-prd → check-version → validate → deploy-hml → hml-dlt-integration-test → create-release-branch → deploy-prod
```

In both workflows, the integration test job **gates** the release branch creation.
