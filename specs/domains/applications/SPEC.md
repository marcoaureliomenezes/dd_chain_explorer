# Spec: Domínio — Applications

> **Status:** Implementado (REST API pendente — ver `rest-api/SPEC.md`)
> **Versão:** 1.0
> **Autor:** Marco Menezes
> **Referências:** `specs/memory/architecture.md`, `specs/memory/tech-stack.md`, `specs/memory/constitution.md`

---

## Escopo

Todas as aplicações Python do DD Chain Explorer:
- **5 streaming jobs** Docker em ECS Fargate (`apps/docker/onchain-stream-txs/`)
- **2 Lambda functions** (`apps/lambda/`)
- **Biblioteca compartilhada** `dm-chain-utils` (`utils/src/dm_chain_utils/`)
- **REST API** FastAPI em ECS Fargate (`apps/rest-api/`) — ver sub-spec `rest-api/`

Este domínio NÃO inclui: infraestrutura Terraform, DABs Databricks, pipelines CI/CD.

---

## Componentes

### Streaming Pipeline — 5 Jobs ECS Fargate

| Job | Replicas | Entrada | Saída |
|-----|----------|---------|-------|
| `1_mined_blocks_watcher` | 1 | Ethereum RPC (Alchemy) | SQS `mainnet-mined-blocks-events` |
| `2_orphan_blocks_watcher` | 1 | SQS + DynamoDB BLOCK_CACHE | SQS (corrigido) |
| `3_block_data_crawler` | 1 | SQS | Firehose `mainnet-blocks-data` + SQS `mainnet-block-txs-hash-id` |
| `4_mined_txs_crawler` | 6 | SQS + DynamoDB SEMAPHORE | Kinesis `mainnet-transactions-data` |
| `5_txs_input_decoder` | 3 | Kinesis | Firehose `mainnet-transactions-decoded` |

**Invariante:** Jobs formam um DAG sequencial — cada job consome a saída do anterior. Quebra em qualquer job interrompe o fluxo downstream.

### Lambda Functions

| Função | Trigger | Propósito |
|--------|---------|-----------|
| `contracts_ingestion` | EventBridge (hourly) | Busca txs de contratos via Etherscan → S3 `raw/batch/` |
| `gold_to_dynamodb` | S3 PutObject trigger | Sincroniza Gold exports → DynamoDB CONSUMPTION entities |

### dm-chain-utils

Biblioteca Python interna publicada no PyPI (`dm-chain-utils >= 0.2.9`). Compartilhada por todos os jobs, Lambdas e batch jobs Databricks.

| Módulo | Classe | Responsabilidade |
|--------|--------|-----------------|
| `dm_dynamodb` | `DMDynamoDB` | Single-table wrapper (CRUD, conditional put, TTL, batch write) |
| `dm_kinesis` | `KinesisHandler` | Producer + consumer Kinesis |
| `dm_sqs` | `SQSHandler` | Producer/consumer SQS com batch |
| `dm_firehose` | `FirehoseHandler` | Firehose Direct Put |
| `dm_cloudwatch_logger` | `CloudWatchLoggingHandler` | JSON estruturado → CloudWatch (buffered) |
| `dm_web3_client` | `Web3Handler` | Web3.py wrapper (blocks + txs) |
| `dm_etherscan` | `EtherscanClient` | Etherscan API v2 (ABI, 4-byte, txlist) |
| `api_keys_manager` | `APIKeysManager` | Semáforo distribuído DynamoDB para rotação de API keys |
| `dm_parameter_store` | `ParameterStoreClient` | SSM Parameter Store wrapper |

---

## Requisitos Funcionais

### Streaming

**FR-APP-001 — Detecção de blocos**
Job 1 deve detectar cada bloco minerado em ≤ 2 segundos via polling `eth_getBlock('latest')` e emitir evento ao SQS.

**FR-APP-002 — Gap recovery**
Se `block_number > prev_block_number + 1`, Job 1 deve emitir eventos para TODOS os blocos intermediários antes do bloco atual.

**FR-APP-003 — Detecção de órfãos**
Job 2 deve verificar hash de cada bloco via RPC e comparar com cache DynamoDB `BLOCK_CACHE` (TTL 1h). Divergência → flag `orphan`.

**FR-APP-004 — Fan-out de transações**
Job 3 deve publicar cada hash de transação do bloco ao SQS `mainnet-block-txs-hash-id` (até `TXS_PER_BLOCK` por bloco).

**FR-APP-005 — Semáforo de API keys**
Job 4 (×6 replicas) deve coordenar via DynamoDB `SEMAPHORE` (TTL 60s) para que cada réplica detenha uma API key Infura exclusiva a cada momento.

**FR-APP-006 — Decodificação 4-stage**
Job 5 deve tentar decodificar calldata em 4 estágios: (1) DynamoDB ABI cache, (2) Etherscan API, (3) 4byte.directory, (4) raw selector. Nunca descartar registro sem tentar todos.

### Lambda

**FR-APP-010 — Entrega particionada**
`contracts_ingestion` deve escrever arquivos S3 em `raw/batch/year=Y/month=M/day=D/hour=H/txs_{address}.json` para compatibilidade com Auto Loader.

**FR-APP-011 — Tolerância a falhas Etherscan**
`contracts_ingestion` deve logar erro e continuar para o próximo contrato em caso de 429 ou erro da API — nunca falhar toda a invocação por um contrato.

**FR-APP-012 — Sincronização Gold → DynamoDB**
`gold_to_dynamodb` deve ler o arquivo JSON exportado pelo `job_export_gold` e escrever entidades `CONSUMPTION` no DynamoDB para consulta pelos jobs de streaming.

### dm-chain-utils

**FR-APP-020 — Versionamento sincronizado**
A versão de `dm-chain-utils` no PyPI deve ser sempre idêntica ao valor do arquivo `VERSION` na raiz do repo. O CI cria tag `v{VERSION}-lib` a cada release.

**FR-APP-021 — Import path canônico**
Todos os consumers devem usar `from dm_chain_utils.<module> import <Class>` — nunca importar de `utils.` diretamente.

---

## Requisitos Não-Funcionais

- **NFR-APP-001:** Nenhum secret hardcoded — API keys lidas do SSM Parameter Store em runtime.
- **NFR-APP-002:** Credenciais AWS em PRD via IAM task role — nunca `AWS_ACCESS_KEY_ID` em containers.
- **NFR-APP-003:** Logging via `CloudWatchLoggingHandler` — nunca `print()` em código de produção.
- **NFR-APP-004:** Deadlock de semáforo DynamoDB deve ser logado e o hash da transação preservado — nunca descartado silenciosamente.

---

## Fora de Escopo (v1)

- Múltiplos providers RPC com failover automático (hoje: Alchemy primário, Infura para txs)
- Schema Registry / Avro — JSON nativo é a escolha (ver ADR-001 em `architecture.md`)
- REST API — ver sub-spec `rest-api/SPEC.md`
