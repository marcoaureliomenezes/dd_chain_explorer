# Infraestrutura Docker Swarm — Data Master On-premises

## 1. Visão Geral

O Docker Swarm é o ambiente de **produção** do projeto. Ele distribui os serviços em um cluster de máquinas físicas, com restrições de placement por nó para garantir que cada camada rodará nos recursos adequados.

O cluster Swarm é composto por **4 nós**:

| Nó                           | Papel     | Hostname                     |
|------------------------------|-----------|------------------------------|
| `marco-Inspiron-15-3511`     | Master    | Ponto de controle do cluster |
| `dadaia-HP-ZBook-15-G2`      | Worker 1  | Kafka, Redis, Spark workers  |
| `dadaia-server-2`            | Worker 2  | MinIO, Nessie, Dremio, Airflow|
| `dadaia-desktop`             | Worker 3  | Spark, visualizer             |

Todos os arquivos de definição de serviços Swarm estão em:

```
dd_chain_explorer/services/swarm/
├── fast_layer.yml
├── lakehouse_layer.yml
├── observability_layer.yml
├── orchestration_layer.yml
├── processing_layer.yml
├── spark_apps_layer.yml
└── conf/
    ├── swarm.kafka.conf
    ├── swarm.lakehouse.conf
    ├── swarm.redis.conf
    └── swarm.secrets.conf
```

A rede Docker virtual utilizada é `vpc_dm` (declarada como `external: true`), criada previamente durante a configuração inicial do cluster.

---

## 2. Arquivos de Configuração e Variáveis de Ambiente

| Arquivo                     | Propósito                                                    |
|-----------------------------|--------------------------------------------------------------|
| `conf/swarm.secrets.conf`   | Credenciais sensíveis (Azure KV, AWS keys, senhas)          |
| `conf/swarm.kafka.conf`     | Endereços dos brokers Kafka e Schema Registry               |
| `conf/swarm.redis.conf`     | Host, porta e senha do Redis                                |
| `conf/swarm.lakehouse.conf` | URLs do MinIO (S3), Nessie, configurações de acesso ao lake |

> **Nota Cloud:** No ambiente Cloud essas variáveis serão substituídas por injeção via AWS Secrets Manager e os endpoints apontarão para serviços gerenciados da AWS/Databricks.

---

## 3. Camadas de Serviços

### 3.1 Camada Fast (`fast_layer.yml`)

**Stack:** `layer_fast`

Contém os serviços responsáveis pela **ingestão em tempo real**: Kafka (mensageria) e Redis (controle de semáforo de API Keys).

#### Serviços:

| Serviço           | Imagem                                     | Nó         | Porta(s)         | Função                                         |
|-------------------|--------------------------------------------|------------|------------------|------------------------------------------------|
| `zookeeper`       | `confluentinc/cp-zookeeper:7.6.0`          | Worker 1   | 2181             | Coordenador do cluster Kafka                   |
| `broker-1`        | `confluentinc/cp-server:7.6.0`             | Master     | 9092 / 29092     | Broker Kafka principal                         |
| `schema-registry` | `confluentinc/cp-schema-registry:7.6.0`    | Master     | 8081             | Registro de schemas Avro                       |
| `control-center`  | `confluentinc/cp-enterprise-control-center:7.6.0` | Master | 9021          | Interface web de gerenciamento Kafka           |
| `redis`           | `redis:7.2`                                | Master     | 16379 → 6379     | Cache para semáforo de API Keys e consumo      |

**Tópicos Kafka utilizados (convenção de nomenclatura):**

```
mainnet.0.application.logs       → logs de aplicação (streaming jobs)
mainnet.0.batch.logs             → logs de jobs batch
mainnet.1.mined_blocks.events    → eventos de bloco minerado
mainnet.2.blocks.data            → dados completos de blocos
mainnet.3.block.txs.hash_id      → hashes de transações por bloco
mainnet.4.transactions.data      → dados completos de transações
```

A convenção de nomenclatura segue o padrão: `<network>.<camada>.<entidade>.<tipo_dado>`

**Configuração do Kafka:**

```yaml
KAFKA_BROKER_ID: 1
KAFKA_ZOOKEEPER_CONNECT: 'zookeeper:2181'
KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
KAFKA_CONFLUENT_SCHEMA_REGISTRY_URL: http://schema-registry:8081
```

> **Nota Cloud:** O Kafka será substituído pelo **Amazon MSK**. O Schema Registry poderá ser gerenciado via **AWS Glue Schema Registry** ou mantido como serviço standalone. O Redis será substituído por **Amazon ElastiCache for Redis** ou **Azure CosmosDB**.

---

### 3.2 Camada Lakehouse (`lakehouse_layer.yml`)

**Stack:** `layer_lakehouse`

Contém os serviços que formam a **arquitetura de armazenamento e consulta** do Data Lake.

#### Serviços:

| Serviço     | Imagem                      | Nó        | Porta(s)     | Função                                                  |
|-------------|-----------------------------|-----------|--------------|---------------------------------------------------------|
| `minio`     | `bitnami/minio:2024.9.22`   | Worker 2  | 9001         | Object Storage compatível com S3 (armazena arquivos Iceberg) |
| `nessie_pg` | `postgres:16`               | Worker 2  | —            | PostgreSQL como backend de metadados do Nessie          |
| `nessie`    | `bitnami/nessie:0.99.0`     | Worker 2  | 19120        | Catálogo de dados com versionamento Git-like (Iceberg)  |
| `dremio`    | `dremio/dremio-oss:25.1`    | Worker 2  | 9047         | Query engine SQL sobre o Data Lake                      |

**Arquitetura Lakehouse:**

```
┌─────────────────────────────────────────────────────┐
│                   CAMADA LAKEHOUSE                   │
│                                                     │
│  MinIO (S3-compatible)                              │
│  ├── s3a://spark/checkpoints/  (checkpoints Spark)  │
│  ├── s3a://raw-data/           (dados raw / staging)│
│  └── s3a://warehouse/          (tabelas Iceberg)    │
│              ↑                                      │
│         Nessie (catálogo Iceberg + versionamento)   │
│              ↑                                      │
│         Dremio (SQL engine / visualização)          │
└─────────────────────────────────────────────────────┘
```

**Configuração do Nessie:**

```yaml
NESSIE_VERSION_STORE_TYPE: JDBC
QUARKUS_DATASOURCE_JDBC_URL: jdbc:postgresql://nessie_pg:5432/nessie
```

> **Nota Cloud:** MinIO → **Amazon S3**, Nessie → **Unity Catalog (Databricks)**, Dremio → **Databricks SQL / SQL Warehouse**.

---

### 3.3 Camada de Observabilidade (`observability_layer.yml`)

**Stack:** `layer_observability`

Contém os serviços de **monitoramento de infraestrutura e aplicações**.

#### Serviços:

| Serviço              | Imagem                                | Nó        | Porta(s) | Função                                       |
|----------------------|---------------------------------------|-----------|----------|----------------------------------------------|
| `prometheus`         | `marcoaureliomenezes/prometheus:1.0.0`| Worker 1  | 9090     | Coleta e armazena métricas                   |
| `grafana`            | `grafana/grafana`                     | Worker 1  | 3000     | Dashboards de monitoramento                  |
| `visualizer`         | `dockersamples/visualizer:stable`     | Worker 3  | 28080    | Visualização do estado do Swarm              |
| `kafka-exporter`     | `danielqsj/kafka-exporter`            | Worker 1  | 9308     | Exporta métricas do Kafka para Prometheus    |
| `cadvisor_master`    | `gcr.io/cadvisor/cadvisor`            | Master    | 38080    | Monitoramento de containers Docker           |
| `cadvisor_worker_1`  | `gcr.io/cadvisor/cadvisor`            | Worker 1  | 38081    | Monitoramento de containers (Worker 1)       |
| `cadvisor_worker_2`  | `gcr.io/cadvisor/cadvisor`            | Worker 2  | 38082    | Monitoramento de containers (Worker 2)       |
| `cadvisor_worker_3`  | `gcr.io/cadvisor/cadvisor`            | Worker 3  | 38083    | Monitoramento de containers (Worker 3)       |
| `node_exporter_*`    | `quay.io/prometheus/node-exporter`    | Todos     | —        | Métricas de sistema operacional dos servidores|

**Fluxo de monitoramento:**

```
cAdvisor (containers) ──→
                          Prometheus ──→ Grafana (dashboards)
Node Exporter (SO) ────→
Kafka Exporter ────────→
```

> **Nota Cloud:** No ambiente Cloud, o monitoramento será feito via **AWS CloudWatch**, **Databricks Observability** e dashboards nativos do MSK.

---

### 3.4 Camada de Orquestração (`orchestration_layer.yml`)

**Stack:** `layer_orchestration`

Apache Airflow configurado para orquestrar todos os jobs batch e processos periódicos.

#### Serviços:

| Serviço              | Imagem                               | Nó        | Porta(s) | Função                                              |
|----------------------|--------------------------------------|-----------|----------|-----------------------------------------------------|
| `airflow_pg`         | `postgres:16`                        | Worker 2  | —        | PostgreSQL — banco de metadados do Airflow          |
| `airflow-apiserver`  | `marcoaureliomenezes/airflow:1.0.0`  | Worker 2  | 8080     | API REST e UI do Airflow                            |
| `airflow-scheduler`  | `marcoaureliomenezes/airflow:1.0.0`  | Worker 2  | —        | Agendador e executor das DAGs                       |
| `airflow-init`       | `marcoaureliomenezes/airflow:1.0.0`  | Worker 2  | —        | Migração e inicialização do banco de dados          |

**Configuração do Airflow:**

```yaml
AIRFLOW__CORE__EXECUTOR: LocalExecutor
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@airflow_pg/airflow
AIRFLOW_CONFIG: '/opt/airflow/config/airflow.cfg'
```

O Airflow possui acesso ao socket Docker (`/var/run/docker.sock`) para executar `DockerOperator` e `DockerSwarmOperator`, que disparam containers de aplicação diretamente.

> **Nota Cloud:** Airflow → **Databricks Workflows** (triggers de Jobs Databricks) ou **AWS MWAA** (Managed Airflow).

---

### 3.5 Camada de Processamento (`processing_layer.yml`)

**Stack:** `layer_processing`

Cluster Apache Spark distribuído para processamento dos dados no Data Lake.

#### Serviços:

| Serviço          | Imagem                             | Nó        | Porta(s)      | Função                              |
|------------------|------------------------------------|-----------|---------------|-------------------------------------|
| `spark-master`   | `marcoaureliomenezes/spark:1.0.0`  | Worker 3  | 18080 / 7077  | Spark Master (UI + porta de jobs)   |
| `spark-worker-1` | `marcoaureliomenezes/spark:1.0.0`  | Worker 1  | —             | Spark Worker (4 GB RAM, 4 cores)    |
| `spark-worker-2` | `marcoaureliomenezes/spark:1.0.0`  | Worker 2  | —             | Spark Worker (4 GB RAM, 4 cores)    |
| `spark-worker-3` | `marcoaureliomenezes/spark:1.0.0`  | Worker 3  | —             | Spark Worker (4 GB RAM, 4 cores)    |
| `spark-worker-4` | `marcoaureliomenezes/spark:1.0.0`  | Worker 3  | —             | Spark Worker adicional              |
| `spark-worker-5` | `marcoaureliomenezes/spark:1.0.0`  | Worker 3  | —             | Spark Worker adicional              |

**Configuração dos workers:**

```yaml
SPARK_MODE: worker
SPARK_MASTER_URL: spark://spark-master:7077
SPARK_WORKER_MEMORY: 4G
SPARK_WORKER_CORES: 4
```

> **Nota Cloud:** Spark cluster standalone → **Databricks Runtime** com clusters gerenciados ou **Serverless Compute**.

---

### 3.6 Camada de Aplicações Spark (`spark_apps_layer.yml`)

**Stack:** `layer_spark_apps`

Jobs Spark Streaming que executam continuamente, consumindo dados do Kafka e escrevendo no Data Lake.

#### Serviços:

| Serviço                               | Script                          | Função                                                        |
|---------------------------------------|---------------------------------|---------------------------------------------------------------|
| `spark-app-apk-comsumption`           | `1_api_key_monitor.py`          | Monitora consumo de API Keys via logs Kafka → Redis           |
| `spark-app-multiplex-bronze`          | `2_job_bronze_multiplex.py`     | Multiplex de tópicos Kafka → tabela Bronze Iceberg            |
| `spark-app-silver-logs`               | `3_job_silver_apps_logs.py`     | Bronze → Silver (logs de aplicação)                           |
| `spark-app-silver-mined-blocks-events`| `4_job_silver_blocks_events.py` | Bronze → Silver (eventos de blocos minerados)                 |
| `spark-app-silver-blocks`             | `5_job_silver_blocks.py`        | Bronze → Silver (dados completos de blocos)                   |
| `spark-app-silver-txs`                | `6_job_silver_transactions.py`  | Bronze → Silver (dados completos de transações)               |

Com placement distribuído pelos nós workers para balancear a carga de processamento.

---

## 4. Comandos Make — Docker Swarm

```makefile
# Configuração do cluster
make preconfig_cluster_swarm   # Pré-configuração dos nós (NFS, rede)
make start_cluster_swarm       # Inicia o cluster Swarm

# Build de imagens
make build_customized          # Build das imagens customizadas (Spark, JupyterLab)
make build_prometheus          # Build da imagem Prometheus
make build_airflow             # Build da imagem Airflow (inclui cópia das DAGs)
make build_apps                # Build das imagens de aplicação

# Publish de imagens
make publish_customized        # Push imagens customizadas → Docker Hub
make publish_apps              # Push imagens de aplicação → Docker Hub

# Deploy das stacks
make deploy_prod_all           # Deploy de todas as stacks (lakehouse, observability, fast, processing)
make deploy_prod_lakehouse     # Deploy da camada lakehouse
make deploy_prod_fast          # Deploy da camada fast (Kafka + Redis)
make deploy_prod_processing    # Deploy da camada de processamento (Spark)
make deploy_prod_observability # Deploy da camada de observabilidade
make deploy_prod_airflow       # Deploy da camada de orquestração (Airflow)
make deploy_prod_spark_apps    # Deploy dos Spark Streaming jobs

# Stop das stacks
make stop_prod_all             # Remove todas as stacks
make stop_prod_lakehouse       # Remove stack lakehouse
make stop_prod_fast            # Remove stack fast
make stop_prod_processing      # Remove stack processing
make stop_prod_airflow         # Remove stack orchestration
make stop_prod_spark_apps      # Remove stack spark_apps

# Monitoramento
make watch_prod_services       # Watch no status dos serviços Swarm
```

---

## 5. Diagrama da Arquitetura Swarm

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                          CLUSTER DOCKER SWARM                                    │
│                                                                                  │
│  ┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐    │
│  │  MASTER NODE        │   │  WORKER 1           │   │  WORKER 2           │    │
│  │  marco-Inspiron     │   │  dadaia-HP-ZBook     │   │  dadaia-server-2    │    │
│  │                     │   │                     │   │                     │    │
│  │  broker-1 (Kafka)   │   │  zookeeper          │   │  minio (S3)         │    │
│  │  schema-registry    │   │  spark-worker-1     │   │  nessie + nessie_pg │    │
│  │  control-center     │   │  kafka-exporter     │   │  dremio             │    │
│  │  redis              │   │  prometheus         │   │  airflow_pg         │    │
│  │  cadvisor_master    │   │  grafana            │   │  airflow-apiserver  │    │
│  │                     │   │  cadvisor_worker_1  │   │  airflow-scheduler  │    │
│  └─────────────────────┘   └─────────────────────┘   └─────────────────────┘    │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐     │
│  │  WORKER 3  (dadaia-desktop)                                             │     │
│  │  spark-master  │  spark-worker-3  │  spark-worker-4  │  spark-worker-5  │     │
│  │  visualizer     │  cadvisor_worker_3                                    │     │
│  └─────────────────────────────────────────────────────────────────────────┘     │
│                                                                                  │
│  ═══════════════════  REDE: vpc_dm (overlay)  ═══════════════════════════════    │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. NFS e Volumes Persistentes

Os volumes persistentes são montados via NFS no caminho `/mnt/nfs/swarm/` em todos os nós:

| Caminho NFS                          | Serviço          | Conteúdo                            |
|--------------------------------------|------------------|-------------------------------------|
| `/mnt/nfs/swarm/zookeeper/`          | zookeeper        | Dados e logs do ZooKeeper           |
| `/mnt/nfs/swarm/kafka_broker_1/`     | broker-1         | Dados do broker Kafka               |
| `/mnt/nfs/swarm/minio/data`          | minio            | Objetos do Object Storage           |
| `/mnt/nfs/swarm/pg_nessie/`          | nessie_pg        | Dados do PostgreSQL do Nessie       |
| `/mnt/nfs/swarm/dremio/data`         | dremio           | Dados e configurações do Dremio     |
| `/mnt/nfs/swarm/pg_airflow/`         | airflow_pg       | Dados do PostgreSQL do Airflow      |
| `/mnt/nfs/swarm/prometheus/`         | prometheus       | Dados das séries temporais          |
| `/mnt/nfs/swarm/grafana/`            | grafana          | Dashboards e configurações          |

---

## 7. Tabela de Equivalências Cloud

| Componente On-premises             | Equivalente Cloud (AWS + Databricks)                  |
|------------------------------------|-------------------------------------------------------|
| Docker Swarm cluster               | Amazon ECS Fargate / EKS                              |
| Kafka + ZooKeeper + Schema Registry | Amazon MSK + AWS Glue Schema Registry               |
| Redis                              | Amazon ElastiCache for Redis                          |
| MinIO (Object Storage)             | Amazon S3                                             |
| Nessie (Iceberg Catalog)           | Unity Catalog (Databricks)                            |
| Dremio (SQL Engine)                | Databricks SQL Warehouse                              |
| Spark cluster standalone           | Databricks Runtime (clusters gerenciados/serverless)  |
| Airflow (LocalExecutor)            | Databricks Workflows / AWS MWAA                       |
| Prometheus + Grafana               | AWS CloudWatch + Managed Grafana                      |
| NFS volumes                        | Amazon EFS (Elastic File System)                      |
| Docker Hub (imagens)               | Amazon ECR (Elastic Container Registry)               |
