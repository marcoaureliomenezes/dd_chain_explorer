# Captura de Dados On-Chain

## Visão Geral

A camada de captura de dados é composta por aplicações Python containerizadas que extraem dados da blockchain Ethereum em tempo real e os publicam em tópicos Kafka. Em produção, elas rodam no **ECS Fargate**. Em desenvolvimento, rodam localmente via Docker Compose.

Existem dois containers distintos:

| Container | Pasta | Propósito |
|-----------|-------|-----------|
| `onchain-stream-txs` | `docker/onchain-stream-txs/` | Captura contínua (streaming) de blocos e transações |
| `onchain-batch-txs` | `docker/onchain-batch-txs/` | Captura em lote de transações históricas de contratos |

---

## 1. onchain-stream-txs — Captura Streaming

### Arquitetura Interna

O container `onchain-stream-txs` abriga 4 aplicações Python que se pipelinam via tópicos Kafka:

```
Blockchain Node (Alchemy / Infura)
    │
    ▼
1_mined_blocks_watcher.py ──────────────────▶ mainnet.1.mined_blocks.events
    │                                               │
2_orphan_blocks_watcher.py ─────────────────────────┘ (monitora orphan blocks)
    │
    ▼ (consume mainnet.1.mined_blocks.events)
3_block_data_crawler.py ────────────────────▶ mainnet.2.blocks.data
                        ────────────────────▶ mainnet.3.block.txs.hash_id
    │
    ▼ (consume mainnet.3.block.txs.hash_id)
4_mined_txs_crawler.py ─────────────────────▶ mainnet.4.transactions.data
```

Todos os apps também produzem logs de aplicação para o tópico `mainnet.0.application.logs`.

---

### App 1 — `mined_blocks_watcher.py`

**Função:** Monitorar a blockchain em tempo real e publicar eventos de blocos minerados.

**Mecanismo:**
- Conecta ao nó Ethereum via WebSocket (Alchemy).
- Assina novos blocos (`eth_subscribe newHeads`).
- Para cada bloco recebido, publica um evento leve com `block_number`, `block_hash`, `parent_hash`, `block_timestamp` e `transaction_count`.

**Saída Kafka:**
| Tópico | Formato | Chave |
|--------|---------|-------|
| `mainnet.1.mined_blocks.events` | AVRO (`1_mined_block_event_schema_avro.json`) | `block_number` |
| `mainnet.0.application.logs` | AVRO (logs) | — |

**Variáveis de ambiente (ECS):**
```
TOPIC_LOGS=mainnet.0.application.logs
TOPIC_MINED_BLOCKS_EVENTS=mainnet.1.mined_blocks.events
CLOCK_FREQUENCY=1
AKV_SECRET_NAME=alchemy-api-key-1
```

---

### App 2 — `orphan_blocks_watcher.py`

**Função:** Detectar blocos órfãos (produzidos mas não incluídos na chain definitiva).

**Mecanismo:**
- Consome o tópico `mainnet.1.mined_blocks.events`.
- Cruza informações de `parent_hash` para identificar forks.
- Publica eventos marcados como orphan no mesmo tópico.

**Variáveis de ambiente (ECS):**
```
TOPIC_LOGS=mainnet.0.application.logs
TOPIC_MINED_BLOCKS_EVENTS=mainnet.1.mined_blocks.events
CONSUMER_GROUP_ID=cg_orphan_block_events
AKV_SECRET_NAME=alchemy-api-key-2
```

---

### App 3 — `block_data_crawler.py`

**Função:** A partir do evento de bloco minerado, buscar os dados completos do bloco (via Alchemy) e extrair os hash IDs de todas as transações.

**Mecanismo:**
- Consome `mainnet.1.mined_blocks.events`.
- Para cada bloco, chama `eth_getBlockByNumber`.
- Publicar dados completos do bloco em `mainnet.2.blocks.data`.
- Particionar os hash IDs das transações e publicá-los em `mainnet.3.block.txs.hash_id` (com particionamento para paralelizar o downstream).

**Saída Kafka:**
| Tópico | Formato | Chave |
|--------|---------|-------|
| `mainnet.2.blocks.data` | AVRO (`2_block_data_schema_avro.json`) | `block_number` |
| `mainnet.3.block.txs.hash_id` | AVRO (`3_transaction_hash_ids_schema_avro.json`) | `tx_hash` |

**Variáveis de ambiente (ECS):**
```
TOPIC_LOGS=mainnet.0.application.logs
TOPIC_MINED_BLOCKS_EVENTS=mainnet.1.mined_blocks.events
TOPIC_MINED_BLOCKS=mainnet.2.blocks.data
TOPIC_TXS_HASH_IDS=mainnet.3.block.txs.hash_id
CONSUMER_GROUP=cg_block_data_crawler
TXS_PER_BLOCK=50
CLOCK_FREQUENCY=1
AKV_SECRET_NAME=alchemy-api-key-2
```

---

### App 4 — `mined_txs_crawler.py`

**Função:** Para cada hash de transação recebido, buscar os dados completos da transação via API Infura e publicar no tópico de transações.

Esta é a aplicação de maior throughput do sistema — consome em paralelo (8 réplicas em produção) para compensar a latência das chamadas HTTP à API blockchain.

**Mecanismo:**
- Consome `mainnet.3.block.txs.hash_id` (múltiplas réplicas, cada uma em partições diferentes).
- Para cada hash, chama `eth_getTransactionByHash` via Infura.
- Gerencia chaves de API via **DynamoDB** (semáforo + consumo).
  - A cada `N` transações, troca a chave de API (round-robin).
  - Verifica se a chave foi "tomada" por outro processo.
  - Libera chaves ociosas do semáforo periodicamente.
- Publica os dados completos em `mainnet.4.transactions.data`.

**Saída Kafka:**
| Tópico | Formato | Chave |
|--------|---------|-------|
| `mainnet.4.transactions.data` | AVRO (`4_transactions_schema_avro.json`) | `tx_hash` |

**Variáveis de ambiente (ECS):**
```
TOPIC_LOGS=mainnet.0.application.logs
TOPIC_TXS_HASH_IDS=mainnet.3.block.txs.hash_id
TOPIC_TXS_DATA=mainnet.4.transactions.data
CONSUMER_GROUP=cg_mined_raw_txs
AKV_SECRET_NAMES=infura-api-key-1-12
```

---

### Schemas Avro

Todos os schemas Avro estão em `docker/onchain-stream-txs/src/schemas/`:

| Arquivo | Tópico |
|---------|--------|
| `0_application_logs_avro.json` | `mainnet.0.application.logs` |
| `1_mined_block_event_schema_avro.json` | `mainnet.1.mined_blocks.events` |
| `2_block_data_schema_avro.json` | `mainnet.2.blocks.data` |
| `3_transaction_hash_ids_schema_avro.json` | `mainnet.3.block.txs.hash_id` |
| `4_transactions_schema_avro.json` | `mainnet.4.transactions.data` |

Em PROD, os schemas são registrados no **AWS Glue Schema Registry**.  
Em DEV, os schemas são registrados no **Confluent Schema Registry** local (`schema-registry:8081`).

---

### Gerenciamento de Chaves de API (DynamoDB)

A aplicação `mined_txs_crawler` usa três tabelas DynamoDB para coordenar o uso de múltiplas chaves de API Infura entre as 8 réplicas:

| Tabela | Uso |
|--------|-----|
| `dm-api-key-semaphore` | Registra qual processo (`PROC_ID`) está usando qual chave |
| `dm-api-key-consumption` | Registra quantas chamadas cada chave fez no dia |
| `dm-popular-contracts` | Usada pelo workflow periódico (não usada aqui) |

O algoritmo de eleição:
1. Checa se a chave atual ainda é "minha" no semáforo.
2. A cada `TXS_THRESHOLD` transações, força rotação da chave.
3. A cada 10 transações, libera chaves ociosas do semáforo.

---

### Dependências Python (`requirements.txt`)

Principais dependências do `onchain-stream-txs`:

```
web3
confluent-kafka
fastavro
boto3              # DynamoDB
dm-33-utils        # lib interna (lib-dm-utils/)
```

---

### Deploy Local (DEV)

```bash
# Subir infraestrutura local primeiro
make deploy_dev_infra

# Subir as aplicações
make deploy_dev_stream

# Acompanhar logs
docker compose -f services/compose/python_streaming_apps_layer.yml logs -f

# Parar
make stop_dev_stream
```

---

## 2. onchain-batch-txs — Captura Batch

### Função

O container `onchain-batch-txs` coordena a ingestão em lote de transações históricas de contratos populares. É executado periodicamente, não em modo contínuo.

Em produção, é invocado pelo **Workflow `dm-periodic-processing`** (passo `ingest_contracts_txs`) no Databricks, não diretamente pelo ECS.

### Estrutura de Scripts

```
docker/onchain-batch-txs/src/
├── batch_ingestion/
│   ├── 1_capture_and_ingest_contracts_txs.py  ← script principal
│   ├── 2_test_new_data.py                     ← validação dos dados ingeridos
│   └── etherscan_utils.py                     ← utilitários para API Etherscan
├── kafka_maintenance/
│   ├── 0_create_topics.py                     ← cria tópicos Kafka (setup)
│   ├── 1_delete_topics.py                     ← deleta tópicos (teardown)
│   └── conf/
│       ├── topics_dev.ini                     ← configuração de tópicos para DEV
│       └── topics_prd.ini                     ← configuração de tópicos para PROD
└── s3_maintenance/
    └── 1_delete_s3_objects.py                 ← limpeza de dados no S3 raw
```

### Script Principal — `1_capture_and_ingest_contracts_txs.py`

**Mecanismo:**
1. Consulta a tabela DynamoDB `dm-popular-contracts` para obter os endereços dos contratos mais transacionados.
2. Para cada contrato, usa a **API Etherscan** para buscar o histórico de transações.
3. Salva os dados brutos no bucket S3 `dm-chain-explorer-raw-data` em formato JSON/Parquet particionado por `ingestion_date`.

**Variáveis de ambiente:**
```
TOPIC_LOGS=mainnet.0.application.logs
AKV_NAME=DMEtherscanAsAService        ← Azure Key Vault com chaves Etherscan
APK_NAME=etherscan-api-key-1
EXEC_DATE=2025-02-01 00:00:00+00:00
S3_BUCKET=raw-data
S3_BUCKET_PREFIX=contracts_transactions
```

### Manutenção de Tópicos Kafka

Para criar os tópicos no Kafka (necessário antes do primeiro uso em DEV):

```bash
# Criar tópicos com base no arquivo de configuração
docker compose -f services/compose/python_streaming_apps_layer.yml run --rm onchain-batch-txs \
  python /app/kafka_maintenance/0_create_topics.py

# Deletar tópicos (teardown)
docker compose -f services/compose/python_streaming_apps_layer.yml run --rm onchain-batch-txs \
  python /app/kafka_maintenance/1_delete_topics.py
```
