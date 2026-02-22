# Jobs Python Batch — Captura Batch de Transações de Contratos

## 1. Objetivo

Os Jobs Python Batch são responsáveis pela **captura periódica de transações de contratos populares da blockchain Ethereum** usando a API da Etherscan. Os dados capturados são armazenados em formato JSON em um bucket S3 (MinIO) para posterior ingestão no Data Lake via Jobs Spark Batch.

Esses jobs são **orquestrados pelo Apache Airflow** com agendamento horário.

---

## 2. Localização do Código

```
docker/app_layer/onchain-batch-txs/
├── Dockerfile
├── requirements.txt
└── src/
    ├── batch_ingestion/
    │   ├── 1_capture_and_ingest_contracts_txs.py  # Job principal de captura
    │   ├── 2_test_new_data.py                      # Testes de validação
    │   └── etherscan_utils.py                      # Utilitários Etherscan (local)
    ├── kafka_maintenance/
    │   ├── 0_create_topics.py                      # Criação de tópicos Kafka
    │   ├── 1_delete_topics.py                      # Deleção de tópicos Kafka
    │   └── conf/
    │       ├── topics_dev.ini                      # Config de tópicos (dev)
    │       └── topics_prd.ini                      # Config de tópicos (prd)
    ├── s3_maintenance/
    │   └── 1_delete_s3_objects.py                  # Limpeza de objetos S3
    └── schemas/
        └── application_logs_avro.json              # Schema Avro para logs
```

---

## 3. Fluxo de Captura Batch

```
┌──────────────────────────────────────────────────────────────────────────────┐
│              PIPELINE BATCH — CONTRATOS ETHEREUM                             │
│                                                                              │
│  AIRFLOW DAG: pipeline_hourly_2_contracts_transactions                       │
│                                                                              │
│  1. [VALIDATE_CACHE]                                                         │
│     └── Verifica se o Redis (DB 3) possui contratos populares em cache       │
│           │                                                                   │
│           ├── Cache válido → [BY_PASS_CACHE_FULLFILMENT]                    │
│           │                                                                   │
│           └── Cache inválido → [GET_POPULAR_CONTRACTS_AND_CACHE_THEM]       │
│               └── Job Spark: 1_get_popular_contracts.py                      │
│                   • Lê silver.transactions_fast                              │
│                   • Calcula contratos mais transacionados                    │
│                   • Salva resultado no Redis DB 3                            │
│                                                                              │
│  2. [CAPTURE_AND_STAGE_TXS_BY_CONTRACT]                                     │
│     └── Job Python: 1_capture_and_ingest_contracts_txs.py                  │
│         • Lê lista de contratos do Redis DB 3                                │
│         • Para cada contrato popular:                                        │
│           → Converte datas de execução em intervalos de blocos               │
│              (via Etherscan API: timestamp → block number)                   │
│           → Busca transações no intervalo de blocos                          │
│           → Salva arquivo JSON particionado no S3                            │
│         • Particionamento: year/month/day/hour/txs_{contract}.json          │
│         • Bucket: s3://raw-data/contracts_transactions/                     │
│                                                                              │
│  3. [INGEST_TX_DATA_TO_BRONZE]                                              │
│     └── Job Spark: 2_ingest_txs_data_to_bronze.py                           │
│         • Lê os JSONs do S3 (raw-data/contracts_transactions)                │
│         • Escreve na tabela Iceberg: bronze.popular_contracts_txs            │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Job Principal: `1_capture_and_ingest_contracts_txs.py`

### Classe `ContractTransactionsCrawler`

```python
class ContractTransactionsCrawler:

    def read_config(self, dynamodb_client, etherscan_client):
        # Configura o cliente Etherscan para busca de transações

    def get_contracts(self):
        # Lê contratos populares do Redis DB 3
        # Ordena por volume de transações (valor do Redis)

    def write_config(self, s3_client, bucket, bucket_prefix):
        # Configura o cliente S3 (boto3) e o caminho de destino

    def interval_config(self, end_date, window_hours=1):
        # Converte EXEC_DATE em intervalo de timestamps Unix
        # Busca os números de bloco correspondentes via Etherscan

    def run(self):
        # Loop por cada contrato popular:
        # 1. Configura nome do arquivo (particionado por data/hora)
        # 2. Busca transações paginando via Etherscan API
        # 3. Salva localmente e faz upload para S3
```

### Particionamento no S3:

```
s3://raw-data/contracts_transactions/
└── year=2025/
    └── month=2/
        └── day=13/
            └── hour=15/
                ├── txs_0xAbc123...json
                └── txs_0xDef456...json
```

### Integração com Etherscan (`EthercanAPI`):

| Método                              | Uso no Job                                              |
|-------------------------------------|---------------------------------------------------------|
| `get_block_by_timestamp()`          | Converte start/end timestamp em block range             |
| `get_contract_tx_by_block_interval()` | Busca transações de um contrato em um range de blocos |

---

## 5. Gerenciamento de Contratos Populares (Redis DB 3)

Os contratos populares são identificados pelo Job Spark `1_get_popular_contracts.py`:

1. Lê a tabela `silver.transactions_fast` no Data Lake
2. Agrupa por endereço de contrato (`to`)
3. Conta o volume de transações por contrato
4. Salva no Redis DB 3: `{contract_address: volume_txs}`

O Job Python lê esses contratos ordenados por volume:

```python
def get_contracts(self):
    data = map(lambda key: (key, redis_client.get(key)), redis_client.keys())
    contracts_sorted = sorted(data, key=lambda x: int(x[1]), reverse=True)
    return list(map(lambda x: x[0], contracts_sorted))
```

---

## 6. Manutenção de Tópicos Kafka (`kafka_maintenance`)

Esta imagem também contém scripts para administração dos tópicos Kafka, executados no início do ambiente pela DAG `pipeline_eventual_1_create_environment.py`:

| Script                    | Função                                             |
|---------------------------|----------------------------------------------------|
| `0_create_topics.py`      | Cria todos os tópicos definidos em `topics_dev.ini`|
| `1_delete_topics.py`      | Deleta os tópicos listados                         |

Configuração de tópicos (`topics_dev.ini`):
```ini
[topic.mainnet.0.application.logs]
num_partitions = 1
replication_factor = 1

[topic.mainnet.1.mined_blocks.events]
num_partitions = 1
replication_factor = 1

[topic.mainnet.4.transactions.data]
num_partitions = 8
replication_factor = 1
```

---

## 7. Logging

Os jobs batch publicam logs de execução em dois locais:
1. **Console** — via `ConsoleLoggingHandler` (visível nos logs do container)
2. **Kafka** — via `KafkaLoggingHandler` no tópico `mainnet.0.batch.logs`

Mensagens de log seguem a estrutura:
```
timestamp;APP_NAME;level;message
```

Exemplo:
```
2025-02-01T15:00:00;CONTRACT_TRANSACTIONS_CRAWLER;INFO;timestamp_start:1738407600;timestamp_end:1738411200
2025-02-01T15:00:01;CONTRACT_TRANSACTIONS_CRAWLER;INFO;block_before:21800000;block_after:21800300
2025-02-01T15:00:02;CONTRACT_TRANSACTIONS_CRAWLER;INFO;API_KEY:etherscan-api-key-2;STATUS_CODE:1
```

---

## 8. Variáveis de Ambiente Necessárias

```bash
# Kafka
KAFKA_BROKERS=broker-1:29092
SCHEMA_REGISTRY_URL=http://schema-registry:8081
TOPIC_LOGS=mainnet.0.application.logs

# Redis (contratos populares)
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASS=secret
REDIS_DB=3

# Azure Key Vault (API Key Etherscan)
AZURE_SUBSCRIPTION_ID=...
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
AKV_NAME=DMEtherscanAsAService
APK_NAME=etherscan-api-key-2

# S3 / MinIO
S3_URL=http://minio:9000
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET=raw-data
S3_BUCKET_PREFIX=contracts_transactions

# Controle de execução
NETWORK=mainnet
EXEC_DATE={{ execution_date }}   # Fornecido pelo Airflow (Jinja templating)
```

---

## 9. Adaptações Necessárias para a Cloud

| Item                       | On-premises                          | Cloud (AWS)                          | Adaptação Necessária                              |
|----------------------------|--------------------------------------|--------------------------------------|--------------------------------------------------|
| Azure Key Vault            | `DefaultAzureCredential` + `SecretClient` | AWS Secrets Manager (`boto3`)   | Substituir `get_secrets.py` por chamadas ao SSM  |
| MinIO (S3)                 | `boto3` com `endpoint_url=http://minio:9000` | `boto3` nativo na AWS         | Remover `endpoint_url` customizado               |
| Redis (contratos)          | Redis local                          | Amazon ElastiCache for Redis         | Alterar variáveis `REDIS_HOST`/`REDIS_PORT`      |
| Deploy                     | Docker Compose / Airflow DockerOperator | Amazon ECS (Fargate)              | Criar task definitions ECS + triggers via Databricks Workflows |
| Orchestration              | Apache Airflow                       | Databricks Workflows                 | Recriar DAGs como workflows Databricks           |
