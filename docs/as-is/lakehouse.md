# Arquitetura Lakehouse — Data Master On-premises

## 1. Visão Geral

O Data Master utiliza uma arquitetura **Open Lakehouse** baseada em tecnologias open-source:

- **Apache Iceberg** como formato de tabela (suporte a ACID, schema evolution, time-travel)
- **Project Nessie** como catálogo de dados — Git-like versioning para tabelas Iceberg
- **MinIO** como Object Storage compatível com S3
- **Apache Spark** como engine de processamento distribuído
- **Dremio** como engine SQL para consultas analíticas sobre o lake

---

## 2. Arquitetura dos Componentes

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        ARQUITETURA LAKEHOUSE                                 │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │                    CAMADA DE ARMAZENAMENTO                          │     │
│  │                                                                     │     │
│  │  MinIO (Object Storage — S3-compatible)                             │     │
│  │  ├── s3a://warehouse/       → Tabelas Iceberg (dados Parquet)       │     │
│  │  ├── s3a://raw-data/        → Dados raw / staging (JSON)            │     │
│  │  └── s3a://spark/           → Checkpoints dos Spark Streaming jobs  │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
│                           │                                                  │
│  ┌────────────────────────▼────────────────────────────────────────────┐     │
│  │                    CAMADA DE CATÁLOGO                               │     │
│  │                                                                     │     │
│  │  Nessie (Iceberg Catalog — versionamento Git-like)                  │     │
│  │  ├── Backend: PostgreSQL (nessie_pg)                                │     │
│  │  ├── Branch: main (produção)                                        │     │
│  │  ├── Namespaces:                                                    │     │
│  │  │   ├── b_fast    → tabelas Bronze (streaming)                     │     │
│  │  │   ├── bronze    → tabelas Bronze (batch)                         │     │
│  │  │   ├── s_apps    → tabelas Silver (dados on-chain)                │     │
│  │  │   ├── s_logs    → tabelas Silver (logs)                          │     │
│  │  │   └── gold      → views e tabelas Gold                           │     │
│  │  └── API REST: http://nessie:19120/api/v1                           │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
│              │                             │                                  │
│  ┌───────────▼────────────┐   ┌───────────▼────────────────────────────┐     │
│  │  CAMADA DE PROCESSAMENTO│   │  CAMADA DE CONSULTA                   │     │
│  │                         │   │                                        │     │
│  │  Apache Spark           │   │  Dremio (SQL Engine)                  │     │
│  │  ├── Spark Master       │   │  ├── Conecta ao MinIO via S3           │     │
│  │  ├── Spark Workers (5x) │   │  ├── Usa Nessie como catálogo         │     │
│  │  ├── Streaming jobs     │   │  └── UI: http://dremio:9047           │     │
│  │  └── Batch jobs         │   │                                        │     │
│  └─────────────────────────┘   └────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. MinIO — Object Storage

**Imagem:** `bitnami/minio:2024.9.22`

MinIO é compatível com a API S3 da AWS, permitindo usar `boto3` e `s3a://` (Spark/Hadoop) sem alterações de código ao migrar para AWS S3.

### Estrutura de Buckets:

| Bucket           | Conteúdo                                              | Acesso                    |
|------------------|-------------------------------------------------------|---------------------------|
| `warehouse`      | Arquivos Parquet das tabelas Iceberg (dados do lake)  | Spark, Nessie, Dremio     |
| `raw-data`       | Arquivos JSON raw — staging de captura batch          | Spark batch, Python batch |
| `spark`          | Checkpoints dos Spark Streaming jobs                  | Spark streaming           |

### Configuração S3 no Spark:

```properties
spark.hadoop.fs.s3a.endpoint=http://minio:9000
spark.hadoop.fs.s3a.access.key=${AWS_ACCESS_KEY_ID}
spark.hadoop.fs.s3a.secret.key=${AWS_SECRET_ACCESS_KEY}
spark.hadoop.fs.s3a.path.style.access=true
spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem
```

### Deploy (Swarm):

```yaml
minio:
  image: bitnami/minio:2024.9.22
  volumes:
    - /mnt/nfs/swarm/minio/data:/bitnami/minio/data
  ports:
    - 9001:9001    # Console web
```

---

## 4. Nessie — Catálogo Iceberg com Versionamento

**Imagem:** `bitnami/nessie:0.99.0`

O Project Nessie é um catálogo de dados com semântica Git-like, permitindo criar branches de dados, commitar alterações e fazer rollback de transformações — fundamental para pipelines de dados confiáveis.

### Configuração no Spark:

```properties
spark.sql.catalog.nessie=org.apache.iceberg.spark.SparkCatalog
spark.sql.catalog.nessie.catalog-impl=org.apache.iceberg.nessie.NessieCatalog
spark.sql.catalog.nessie.uri=http://nessie:19120/api/v1
spark.sql.catalog.nessie.ref=main
spark.sql.catalog.nessie.authentication.type=NONE
spark.sql.catalog.nessie.warehouse=s3a://warehouse/
spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions
```

### Backend PostgreSQL:

```yaml
nessie_pg:
  image: postgres:16
  environment:
    POSTGRES_USER: nessie
    POSTGRES_PASSWORD: nessie
    POSTGRES_DB: nessie

nessie:
  image: bitnami/nessie:0.99.0
  environment:
    NESSIE_VERSION_STORE_TYPE: JDBC
    QUARKUS_DATASOURCE_JDBC_URL: jdbc:postgresql://nessie_pg:5432/nessie
```

### Namespaces e Tabelas:

| Namespace | Escopo        | Tabelas principais                                          |
|-----------|---------------|-------------------------------------------------------------|
| `b_fast`  | Bronze Fast   | `kafka_topics_multiplexed`                                  |
| `bronze`  | Bronze Batch  | `popular_contracts_txs`                                     |
| `s_apps`  | Silver Apps   | `mined_blocks_events`, `blocks_fast`, `blocks_txs_fast`, `transactions_fast` |
| `s_logs`  | Silver Logs   | `apps_logs_fast`                                            |
| `gold`    | Gold          | Views analíticas                                            |

---

## 5. Apache Spark — Engine de Processamento

**Imagem:** `marcoaureliomenezes/spark:1.0.0` (customizada a partir do `bitnami/spark`)

O cluster Spark é configurado no modo **Standalone**, com 1 Master e até 5 Workers distribuídos pelos nós do cluster Swarm.

### Configuração do Cluster:

| Serviço       | Nó        | Recursos             | Porta       |
|---------------|-----------|----------------------|-------------|
| spark-master  | Worker 3  | —                    | 7077, 18080 |
| spark-worker-1| Worker 1  | 4 GB RAM, 4 cores    | —           |
| spark-worker-2| Worker 2  | 4 GB RAM, 4 cores    | —           |
| spark-worker-3| Worker 3  | 4 GB RAM, 4 cores    | —           |
| spark-worker-4| Worker 3  | 4 GB RAM, 4 cores    | —           |
| spark-worker-5| Worker 3  | 4 GB RAM, 4 cores    | —           |

### SparkSession com Iceberg + Nessie:

```python
# dm_33_utils/spark_utils.py
class SparkUtils:
    @staticmethod
    def get_spark_session(logger, app_name) -> SparkSession:
        spark = (
            SparkSession
            .builder
            .appName(app_name)
            .master(os.getenv("SPARK_MASTER_URL"))
            .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
            .config("spark.sql.catalog.nessie", "org.apache.iceberg.spark.SparkCatalog")
            .config("spark.sql.catalog.nessie.catalog-impl", "org.apache.iceberg.nessie.NessieCatalog")
            .config("spark.sql.catalog.nessie.uri", os.getenv("NESSIE_URI"))
            .config("spark.sql.catalog.nessie.warehouse", "s3a://warehouse/")
            .config("spark.hadoop.fs.s3a.endpoint", os.getenv("S3_URL"))
            .config("spark.hadoop.fs.s3a.access.key", os.getenv("AWS_ACCESS_KEY_ID"))
            .config("spark.hadoop.fs.s3a.secret.key", os.getenv("AWS_SECRET_ACCESS_KEY"))
            .config("spark.hadoop.fs.s3a.path.style.access", "true")
            .getOrCreate()
        )
        return spark
```

---

## 6. Dremio — SQL Engine Analítico

**Imagem:** `dremio/dremio-oss:25.1`

O Dremio é a camada de **consulta SQL** sobre o Data Lake, permitindo que analistas e cientistas de dados interajam com as tabelas Iceberg via SQL padrão, sem precisar usar Spark.

### Funcionalidades:

- Conecta diretamente ao MinIO (source S3) e ao Nessie (catálogo)
- Suporte a queries federadas (múltiplas fontes)
- Interface web em `http://dremio:9047`
- Suporte nativo ao formato Iceberg via Nessie

### Integração com JupyterLab:

Os notebooks em `mnt/jupyterlab/trino-notebooks` demonstram o uso de Trino (alternativa ao Dremio) para consultas SQL sobre o lake.

---

## 7. Fluxo de Dados — Visão Completa

```
ETHEREUM BLOCKCHAIN
       │
       ▼ (Web3.py)
KAFKA TOPICS
├── mainnet.0.application.logs
├── mainnet.1.mined_blocks.events
├── mainnet.2.blocks.data
├── mainnet.3.block.txs.hash_id
└── mainnet.4.transactions.data
       │
       ▼ (Spark Streaming)
CAMADA BRONZE (MinIO/Iceberg)
└── b_fast.kafka_topics_multiplexed
    (dados raw, Avro serializado)
       │
       ▼ (Spark Streaming)
CAMADA SILVER (MinIO/Iceberg)
├── s_apps.mined_blocks_events
├── s_apps.blocks_fast
├── s_apps.blocks_txs_fast
├── s_apps.transactions_fast
└── s_logs.apps_logs_fast
    (dados parseados, schema definido)
       │
       ▼ (Spark Batch / DDL)
CAMADA GOLD (MinIO/Iceberg)
└── gold.* (views analíticas)
    (dados agregados, prontos para BI)
       │
       ▼ (Dremio / JupyterLab)
CONSUMO ANALÍTICO
```

---

## 8. Apache Iceberg — Recursos Utilizados

O formato Iceberg é usado em todas as tabelas do lake. Os recursos mais relevantes do projeto:

| Recurso               | Uso no Projeto                                                       |
|-----------------------|----------------------------------------------------------------------|
| **Particionamento**   | `dat_ref` (string `yyyy-MM-dd`) nas tabelas Bronze                   |
| **Schema Evolution**  | Suportado nativamente — campos podem ser adicionados sem reprocessamento |
| **ACID Transactions** | Escritas concorrentes de múltiplos jobs Streaming seguras            |
| **Time Travel**       | Consultável via `VERSION AS OF {snapshot_id}` ou `TIMESTAMP AS OF` |
| **Compactação**       | `CALL system.rewrite_data_files()` — executado pelo job de manutenção |
| **Expire Snapshots**  | `CALL system.expire_snapshots()` — controla retenção de metadados   |
| **Streaming Writes**  | `writeStream.format("iceberg").toTable()` nos jobs Spark Streaming  |

---

## 9. Tabela de Equivalências Cloud

| Componente On-premises             | Equivalente Cloud (AWS + Databricks)                 | Observações                                          |
|------------------------------------|------------------------------------------------------|------------------------------------------------------|
| MinIO (Object Storage)             | **Amazon S3**                                        | Remoção de `endpoint_url` e `path.style.access`     |
| Nessie + PostgreSQL (catálogo)     | **Databricks Unity Catalog**                        | Metastore gerenciado; remoção da config Nessie       |
| Dremio (SQL Engine)                | **Databricks SQL Warehouse**                        | Conecta ao UC nativamente                             |
| Apache Spark Standalone (1 master, 5 workers) | **Databricks Runtime** (cluster gerenciado ou serverless) | Sem gestão de cluster; `spark` disponível no contexto |
| Iceberg format                     | **Delta Lake** (nativo Databricks) ou **Iceberg no UC** | Delta Lake preferido; Iceberg suportado via UC    |
| `rewrite_data_files` (Iceberg)     | `OPTIMIZE` (Delta Lake)                              | Databricks faz OPTIMIZE automático                   |
| `expire_snapshots` (Iceberg)       | `VACUUM` (Delta Lake)                                | Configurável via `delta.logRetentionDuration`        |
| NFS volumes                        | **Amazon EFS**                                       | Volumes persistentes para checkpoints e dados        |
