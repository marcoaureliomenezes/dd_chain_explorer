# Infraestrutura de Serviços da Camada de Aplicação

## 1. Visão Geral

A camada de aplicação é composta por **4 tipos de serviços** distintos, todos containerizados em imagens Docker publicadas no Docker Hub:

| Imagem Docker                                   | Tipo             | Fonte de código                                        |
|-------------------------------------------------|-----------------|--------------------------------------------------------|
| `marcoaureliomenezes/onchain-batch-txs`         | Python Batch    | `docker/app_layer/onchain-batch-txs`                   |
| `marcoaureliomenezes/dm-onchain-stream-txs`     | Python Streaming| `docker/app_layer/onchain-stream-txs`                  |
| `marcoaureliomenezes/spark-batch-jobs`          | Spark Batch     | `docker/app_layer/spark-batch-jobs`                    |
| `marcoaureliomenezes/spark-streaming-jobs`      | Spark Streaming | `docker/app_layer/spark-streaming-jobs`                |

As imagens de serviços de suporte são:

| Imagem Docker                          | Serviço           | Fonte                                        |
|----------------------------------------|------------------|----------------------------------------------|
| `marcoaureliomenezes/spark`            | Spark Cluster    | `docker/customized/spark`                    |
| `marcoaureliomenezes/airflow`          | Airflow          | `docker/customized/airflow`                  |
| `marcoaureliomenezes/prometheus`       | Prometheus       | `docker/customized/prometheus`               |
| `marcoaureliomenezes/rosemberg`        | JupyterLab       | `docker/customized/jupyterlab`               |

---

## 2. Estrutura de Diretórios das Imagens

```
docker/
├── app_layer/
│   ├── onchain-batch-txs/          # Jobs Python batch
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── batch_ingestion/    # Scripts de captura batch
│   │       ├── kafka_maintenance/  # Criação/deleção de tópicos Kafka
│   │       ├── s3_maintenance/     # Manutenção de objetos S3
│   │       └── schemas/            # Schemas Avro
│   │
│   ├── onchain-stream-txs/         # Jobs Python streaming
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── 1_mined_blocks_watcher.py
│   │       ├── 2_orphan_blocks_watcher.py
│   │       ├── 3_block_data_crawler.py
│   │       ├── 4_mined_txs_crawler.py
│   │       ├── configs/            # Configurações Kafka (producers/consumers .ini)
│   │       ├── schemas/            # Schemas Avro por tópico
│   │       └── utils/              # Utilitários (API keys, Kafka, Web3, Secrets)
│   │
│   ├── spark-batch-jobs/           # Jobs Spark batch
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── ddl_iceberg_tables/ # DDL para criação das tabelas Iceberg
│   │       ├── maintenance_streaming_tables/ # Manutenção das tabelas Iceberg
│   │       ├── periodic_spark_processing/    # Jobs de processamento periódico
│   │       └── utils/              # Utilitários Spark e Iceberg
│   │
│   └── spark-streaming-jobs/       # Jobs Spark streaming
│       ├── Dockerfile
│       ├── requirements.txt
│       └── src/
│           ├── pyspark/            # Jobs PySpark streaming
│           ├── utils/              # Utilitários (DM schemas, Spark utils)
│           └── i_dm_streaming.py   # Interface base para jobs streaming
│
└── customized/                     # Imagens customizadas de serviços
    ├── airflow/                    # Airflow com providers adicionais
    ├── jupyterlab/                 # JupyterLab com Spark/Trino
    ├── spark/                      # Spark com suporte Iceberg + MinIO
    ├── postgres/                   # PostgreSQL com scripts de inicialização
    └── prometheus/                 # Prometheus com configuração customizada
```

---

## 3. Dependências — Biblioteca `dm-33-utils`

Todas as imagens de aplicação dependem da biblioteca interna `lib-dm-utils`, que é publicada no PyPI como `dm-33-utils`. Ela encapsula os utilitários comuns de integração com os serviços do projeto.

### Módulos da lib:

| Módulo                 | Função                                                                    |
|------------------------|---------------------------------------------------------------------------|
| `dm_utils.py`          | Utilitários gerais (conversão HexBytes→str, etc.)                        |
| `web3_utils.py`        | Conexão com nós Ethereum via Web3.py (Alchemy/Infura), parse de blocos e transações |
| `etherscan_utils.py`   | Cliente da API Etherscan (transações de contratos, logs, timestamps→bloco) |
| `kafka_utils.py`       | Criação de producers/consumers Avro com Confluent Kafka + Schema Registry |
| `kafka_admin_client.py`| Administração de tópicos Kafka (criar, listar, deletar)                  |
| `schema_reg_utils.py`  | Integração com o Schema Registry (obter schema por subject)               |
| `logger_utils.py`      | Handlers de logging (console e Kafka — `ConsoleLoggingHandler`, `KafkaLoggingHandler`) |
| `spark_utils.py`       | Criação de `SparkSession` configurada com Iceberg + MinIO                 |

### Importação nas imagens (`requirements.txt`):

```
dm-33-utils  # ou dm_33_utils (dependendo da versão)
```

> **Nota Cloud:** Para a versão Cloud, a lib será adaptada para conectar-se ao **Amazon MSK** (em vez do Kafka local) e ao **AWS Glue Schema Registry** (em vez do Confluent Schema Registry local). A lógica de negócio permanece inalterada.

---

## 4. Imagens Customizadas de Serviços (`docker/customized`)

### 4.1 Airflow (`docker/customized/airflow`)

Imagem baseada na oficial do Apache Airflow, com:
- Providers adicionais: `apache-airflow-providers-docker`, `apache-airflow-providers-cncf-kubernetes`
- DAGs copiadas para dentro da imagem durante o build via `scripts/cp_airflow_dags.sh`
- Configurações adicionais em `mnt/airflow/config/airflow.cfg`

### 4.2 JupyterLab (`docker/customized/jupyterlab`)

JupyterLab configurado para uso com:
- Apache Spark (via `spark-defaults.conf`)
- Trino (via `trino-notebooks`)
- Notebooks de exploração em `mnt/jupyterlab/spark-notebooks`

### 4.3 Spark (`docker/customized/spark`)

Imagem Spark customizada com suporte a:
- Apache Iceberg (tabelas no formato Iceberg)
- Integração com MinIO (endpoint S3-compatible)
- Nessie como catálogo de metadados

### 4.4 Prometheus (`docker/customized/prometheus`)

Imagem Prometheus com arquivo de configuração `prometheus.yml` que define os targets de scraping (Kafka exporter, Node exporters, cAdvisors).

---

## 5. Deploy das Imagens — Ambientes

| Imagem                           | Compose (dev)                           | Swarm (prod)                         |
|----------------------------------|-----------------------------------------|--------------------------------------|
| `onchain-batch-txs`              | `batch_apps_layer.yml`                  | Via DockerOperator no Airflow        |
| `onchain-stream-txs`             | `python_streaming_apps_layer.yml`       | Manual / Via Airflow                 |
| `spark-batch-jobs`               | `batch_apps_layer.yml`                  | Via DockerOperator no Airflow        |
| `spark-streaming-jobs`           | `spark_streaming_apps_layer.yml`        | `spark_apps_layer.yml`               |
| `airflow`                        | `orchestration_layer.yml`               | `orchestration_layer.yml`            |

---

## 6. Serviços Periféricos Necessários

Os serviços abaixo são dependências externas das aplicações:

| Serviço              | Papel                                                                          | Equivalente Cloud              |
|----------------------|--------------------------------------------------------------------------------|-------------------------------|
| **Kafka + Schema Registry** | Mensageria para dados de streaming; schemas Avro gerenciados            | Amazon MSK + Glue Schema Registry |
| **Redis**            | Semáforo e controle de consumo de API Keys; cache de contratos populares        | Amazon ElastiCache for Redis  |
| **MinIO (S3)**       | Armazenamento de dados raw (staging) e checkpoints dos jobs Spark               | Amazon S3                     |
| **Nessie**           | Catálogo de metadados para tabelas Iceberg com versionamento                    | Databricks Unity Catalog      |
| **Spark Cluster**    | Processamento distribuído dos dados no Data Lake                                | Databricks Runtime            |
| **Airflow**          | Orquestração dos jobs batch com agendamentos e dependências                     | Databricks Workflows          |
| **Azure Key Vault**  | Armazenamento de API Keys (Alchemy, Infura, Etherscan) e credenciais            | AWS Secrets Manager           |
