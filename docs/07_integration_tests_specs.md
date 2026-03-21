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

### `deploy_lambda_functions.yml`
```
branch-guard → check-infra-prd → check-version → build-artifacts → hml-test → create-release-branch → prod-deploy
```

In all workflows, the integration test job **gates** the release branch creation.

---

## 4. Lambda Functions

### 4.1 Inventário de Funções Lambda

| Função | Handler | Localização | Trigger | Ambiente |
|--------|---------|-------------|---------|---------|
| `contracts_ingestion` | `handler.handler` | `lambda/contracts_ingestion/handler.py` | EventBridge Scheduler (1 hora) | PRD |
| `gold_to_dynamodb` | `handler.handler` | `lambda/gold_to_dynamodb/handler.py` | S3 PutObject em `exports/gold_api_keys/*.json` | DEV + PRD |

> **Regra de organização**: Todo código Lambda deve residir em `lambda/<nome_da_funcao>/handler.py`. Funções fora desta estrutura devem ser movidas antes do próximo deploy.

---

### 4.2 `contracts_ingestion` — Fluxo de Dados

```
EventBridge (hourly)
  → handler(event)
  → SSM /etherscan-api-keys          (lê API keys Etherscan)
  → DynamoDB.query(pk="CONTRACT")    (lê lista de contratos populares)
  → for each contract:
      Etherscan.get_block_by_timestamp(start, end)  → block interval
      Etherscan.get_contract_txs_by_block_interval  → transações
      S3.put_object(bucket, "batch/year=.../txs_{contract}.json")
  → return {contracts_processed, total_txs}
```

**Dependências externas**: SSM, DynamoDB, Etherscan API (pública), S3 raw bucket.
**Pré-condição**: DynamoDB deve ter itens `pk=CONTRACT` (populados pela Gold MV `popular_contracts_ranking` via workflow Databricks).

---

### 4.3 `contracts_ingestion` — Teste HML CI/CD Gate (dry_run)

**Workflow**: `deploy_lambda_functions.yml` → job `hml-test`
**Função ephêmera**: `hml-contracts-ingestion-{run_id}`
**Payload**: `{"dry_run": true}`

| # | Check | Condição | Severidade |
|---|-------|----------|-----------|
| 1 | SSM `/etherscan-api-keys` | ≥ 1 key encontrada | **FAIL** (bloqueia) |
| 2 | DynamoDB conectável | Query executada sem erro | **FAIL** (bloqueia) |
| 3 | CONTRACT items | ≥ 1 item em DynamoDB | WARNING (não bloqueia) |
| 4 | FunctionError | ausente | **FAIL** (bloqueia) |
| 5 | statusCode | 200 | **FAIL** (bloqueia) |

**Pass criteria**: checks 1, 2, 4 e 5 OK (check 3 é warning — novo ambiente pode não ter contratos ainda).
**Teardown**: Lambda ephêmera + Layer deletados no step `HML Teardown` (sempre executa).

---

### 4.4 `contracts_ingestion` — Teste Manual Full (pós-deploy PROD)

Execute após deploy PROD para validar o ciclo completo:

```bash
# Invocar com exec_date da última hora
EXEC_DATE=$(date -u -d '1 hour ago' '+%Y-%m-%d %H:00:00+0000')
aws lambda invoke \
  --function-name dm-dd-chain-explorer-prd-contracts-ingestion \
  --payload "{\"exec_date\": \"${EXEC_DATE}\"}" \
  /tmp/contracts-response.json \
  --region sa-east-1
cat /tmp/contracts-response.json
```

| # | Check | Condição |
|---|-------|----------|
| 1 | statusCode | 200 |
| 2 | contracts_processed | ≥ 1 |
| 3 | S3 `batch/year=.../txs_{contract}.json` | ≥ 1 arquivo criado (verificar via `aws s3 ls`) |
| 4 | CloudWatch Logs | `contracts_processed > 0`, sem ERROR |

```bash
# Verificar S3
aws s3 ls s3://<raw-bucket>/batch/ --recursive | grep "txs_" | tail -5
# Verificar logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/dm-dd-chain-explorer-prd-contracts-ingestion \
  --filter-pattern "contracts_processed" \
  --start-time $(date -d '10 minutes ago' +%s000) \
  --region sa-east-1
```

---

### 4.5 `gold_to_dynamodb` — Fluxo de Dados

```
S3 PutObject (exports/gold_api_keys/*.json)
  → handler(event)
  → for each S3 record:
      S3.get_object(bucket, key)         → lê NDJSON (uma linha = um item)
      for each line:
        parse JSON → {source, api_key_name, calls_*, vendor, ...}
        DynamoDB.batch_writer.put_item(pk="CONSUMPTION", sk="{source}#{api_key_name}")
  → return {statusCode: 200, records_processed: N}
```

**Dependências externas**: S3 (leitura), DynamoDB (escrita).
**Trigger no PROD**: S3 notification no bucket `dm-chain-explorer-lakehouse` com prefix `exports/gold_api_keys/` e suffix `.json`.

---

### 4.6 `gold_to_dynamodb` — Teste HML CI/CD Gate (fixture-based)

**Workflow**: `deploy_lambda_functions.yml` → job `hml-test`
**Função ephêmera**: `hml-gold-to-dynamodb-{run_id}`

**Fixture JSON** (uploaded a `exports/gold_api_keys/hml-test-{run_id}.json`):
```json
{"source":"hml-test","api_key_name":"test-key-001","calls_total":42,"calls_ok_total":40,"calls_error_total":2,"calls_24h":10,"vendor":"etherscan","computed_at":"2026-01-01T00:00:00"}
```

| # | Check | Condição | Severidade |
|---|-------|----------|-----------|
| 1 | FunctionError | ausente | **FAIL** (bloqueia) |
| 2 | records_processed | ≥ 1 | **FAIL** (bloqueia) |
| 3 | DynamoDB item | `pk=CONSUMPTION, sk=hml-test#test-key-001` existe | **FAIL** (bloqueia) |

**Pass criteria**: todos os 3 checks OK.
**Teardown**: Lambda ephêmera + S3 fixture + DynamoDB test item deletados no step `HML Teardown` (sempre executa).

---

### 4.7 `gold_to_dynamodb` — Teste Manual Full (pós-deploy PROD)

O trigger real ocorre quando o workflow Databricks executa o job `export_gold_to_s3`:

```bash
# Verificar se o trigger S3 está configurado
aws s3api get-bucket-notification-configuration \
  --bucket dm-chain-explorer-lakehouse \
  --region sa-east-1 | jq '.LambdaFunctionConfigurations'

# Após execução do job Databricks — verificar itens no DynamoDB
aws dynamodb query \
  --table-name dm-chain-explorer \
  --key-condition-expression "pk = :pk" \
  --expression-attribute-values '{":pk":{"S":"CONSUMPTION"}}' \
  --region sa-east-1 \
  --query 'Items[*].{source:source.S,key:sk.S,calls:calls_total.S}' \
  --output table

# Verificar logs Lambda
aws logs filter-log-events \
  --log-group-name /aws/lambda/dm-dd-chain-explorer-prd-gold-to-dynamodb \
  --filter-pattern "records_processed" \
  --start-time $(date -d '30 minutes ago' +%s000) \
  --region sa-east-1
```

| # | Check | Condição |
|---|-------|----------|
| 1 | S3 notification configurada | `LambdaFunctionConfigurations` não vazio |
| 2 | Lambda invocada | CloudWatch Logs com `records_processed > 0` |
| 3 | DynamoDB items | `pk=CONSUMPTION` com ≥ 2 itens distintos |
