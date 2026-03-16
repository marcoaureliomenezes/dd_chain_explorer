# 01 — Arquitetura do DD Chain Explorer

## Visão Geral

O **DD Chain Explorer** é uma plataforma de engenharia de dados em tempo real para extração, processamento e análise de transações e blocos da blockchain Ethereum. A arquitetura segue um modelo de ingestão em camadas:

1. **Captura on-chain** — Serviços Python containerizados que extraem dados da Ethereum via APIs Web3 (Alchemy/Infura) e publicam em tópicos Kafka.
2. **Streaming & Ingestão** — Apache Kafka como barramento de eventos; Spark Streaming para ingestão no S3 (DEV) ou leitura direta pelo Databricks (PROD).
3. **Processamento analítico** — Delta Live Tables (DLT) no Databricks implementando arquitetura medalhão (Bronze → Silver → Gold).
4. **Orquestração** — Apache Airflow para agendamento de jobs batch e trigger de pipelines DLT.

```
Ethereum Mainnet
    │  (RPC via Alchemy/Infura)
    ▼
┌──────────────────────────────────────────┐
│  CAMADA DE CAPTURA (5 Jobs Python)       │
│  ├─ 1_mined_blocks_watcher              │
│  ├─ 2_orphan_blocks_watcher             │
│  ├─ 3_block_data_crawler                │
│  ├─ 4_mined_txs_crawler (6 réplicas)    │
│  └─ 5_txs_input_decoder                 │
└──────────────┬───────────────────────────┘
               ▼
┌──────────────────────────────────────────┐
│  APACHE KAFKA (6 tópicos Avro)           │
│  ├─ mainnet.0.application.logs           │
│  ├─ mainnet.1.mined_blocks.events        │
│  ├─ mainnet.2.blocks.data                │
│  ├─ mainnet.3.block.txs.hash_id          │
│  ├─ mainnet.4.transactions.data          │
│  └─ mainnet.5.txs.input_decoded          │
└──────────────┬───────────────────────────┘
               ▼
┌──────────────────────────────────────────┐
│  INGESTÃO                                │
│  DEV:  Spark → S3 Parquet multiplex      │
│  PROD: Databricks lê Kafka direto (MSK)  │
└──────────────┬───────────────────────────┘
               ▼
┌──────────────────────────────────────────┐
│  DATABRICKS — Delta Live Tables          │
│  ├─ Bronze: kafka_topics_multiplexed     │
│  ├─ Silver: blocos, transações, logs     │
│  └─ Gold: contratos populares, gas, etc. │
└──────────────────────────────────────────┘
```

---

## Componentes Principais

### 1. Serviços de Captura (Streaming)

Cinco jobs Python executam em containers Docker e formam uma pipeline encadeada de extração de dados on-chain. Cada job consome de um tópico Kafka e produz para o próximo, usando serialização Avro com Schema Registry.

- **Job 1 (Mined Blocks Watcher)**: Detecta blocos recém-minerados via polling RPC.
- **Job 2 (Orphan Blocks Watcher)**: Verifica finalidade de blocos e detecta reorganizações (reorgs) usando cache DynamoDB.
- **Job 3 (Block Data Crawler)**: Busca dados completos de blocos e distribui hashes de transações em 8 partições Kafka.
- **Job 4 (Mined Txs Crawler)**: Busca dados brutos de transações com **6 réplicas** usando rotação distribuída de API keys via semáforo DynamoDB.
- **Job 5 (Txs Input Decoder)**: Decodifica o campo `input` de transações usando ABIs do Etherscan, 4byte.directory e cache DynamoDB.

Um job periódico no Databricks exporta métricas Gold de consumo de API keys para S3, onde uma Lambda sincroniza com o DynamoDB.

### 2. Apache Kafka

Barramento central de eventos. Todos os dados fluem entre jobs via tópicos Kafka com serialização Avro e Schema Registry Confluent.

| Tópico | Partições | Descrição |
|--------|-----------|-----------|
| `mainnet.0.application.logs` | 1 | Logs estruturados de todos os jobs |
| `mainnet.1.mined_blocks.events` | 1 | Eventos de blocos minerados e órfãos |
| `mainnet.2.blocks.data` | 1 | Dados completos de blocos (18+ campos) |
| `mainnet.3.block.txs.hash_id` | 8 | Hashes de transações para paralelismo |
| `mainnet.4.transactions.data` | 8 | Dados brutos de transações |
| `mainnet.5.txs.input_decoded` | 4 | Transações com input decodificado |

### 3. Spark Streaming (DEV)

Um job Spark Structured Streaming atende necessidade específica do ambiente DEV:

- **Kafka → S3 Multiplex**: Lê 5 tópicos Kafka simultaneamente e escreve Parquet particionado por `topic_name` no S3, criando a ponte entre o ambiente local e o Databricks Free Edition.

### 4. Databricks (DLT)

Processamento analítico implementado com Delta Live Tables seguindo arquitetura medalhão:

- **Bronze**: Ingestão bruta dos tópicos Kafka (via S3 em DEV, via MSK direto em PROD).
- **Silver**: Deserialização Avro, limpeza, enriquecimento e joins stream-static.
- **Gold**: Materialized views — contratos populares, transações P2P, consumo de gas, consumo de API keys.

### 5. Orquestração (Airflow)

Apache Airflow roda como container Docker (LocalExecutor) e executa:

- **A cada 5 min**: Trigger dos pipelines DLT Ethereum e App Logs (workaround para Free Edition que não suporta DLT contínuo).
- **A cada hora**: Ingestão batch de transações de contratos populares via Etherscan.
- **A cada 12h**: Manutenção de tabelas (OPTIMIZE + VACUUM).
- **Eventual**: Setup/teardown de ambiente (criação de tópicos Kafka, tabelas Databricks).

---

## Ambientes: DEV vs PROD

### Correlação de Componentes

| Componente | DEV (Local) | PROD (AWS) |
|------------|-------------|------------|
| **Kafka** | Container Docker (Confluent KRaft, single-node) | Amazon MSK (2 brokers, kafka.t3.small, multi-AZ) |
| **Schema Registry** | Container Docker (Confluent) | ECS Fargate + Cloud Map DNS |
| **DynamoDB** | AWS DynamoDB (single-table `dm-chain-explorer`, credenciais ~/.aws) | AWS DynamoDB (single-table `dm-chain-explorer`, IAM task role) |
| **Jobs Python (streaming)** | Docker Compose na rede `vpc_dm` | ECS Fargate (5 services, awsvpc mode) |
| **Spark Streaming** | Container Docker (local mode) — Kafka→S3 multiplex | *Sem equivalente direto — DLT fãz ingestão direta do MSK* |
| **Databricks** | Free Edition (Community Cloud) | Workspace AWS (Terraform-provisioned, Unity Catalog) |
| **S3 Storage** | Bucket `dm-chain-explorer-dev-ingestion` | 3 buckets: raw, lakehouse, databricks |
| **Airflow** | Docker Compose (LocalExecutor, porta 8090) | Docker Compose (LocalExecutor, porta 8091) *ou MWAA* |
| **API Keys** | AWS SSM Parameter Store (compartilhado) | AWS SSM Parameter Store (mesmo) |
| **Monitoramento** | Control Center (Kafka UI, porta 9021) | CloudWatch Logs |

### Ambiente DEV — Topologia de Rede

O ambiente de DEV opera em **duas redes isoladas**:

**1. Rede local Docker (`vpc_dm`)**
```
┌─── Rede Docker: vpc_dm ────────────────────────────────────┐
│                                                             │
│  kafka-broker-1 ◄──► schema-registry ◄──► control-center   │
│       ▲                                                     │
│       │                                                     │
│  python-job-* (5 jobs streaming)                            │
│  spark-app-kafka-s3 (1 job spark)                           │
│  spark-master ◄──► spark-worker-1                           │
│  airflow-scheduler / airflow-webserver / airflow-postgres   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Portas expostas no host:
- `29092` — Kafka (acesso externo)
- `8081` — Schema Registry
- `9021` — Control Center UI
- `8080` — Spark Master UI
- `8090` — Airflow Webserver

**2. Rede Databricks Free Edition (Cloud)**
- Workspace em `https://community.cloud.databricks.com` (ou `dbc-*.cloud.databricks.com`)
- Acessa dados via External Location no S3 (bucket DEV)
- Sem conectividade direta com o Kafka local → dados chegam via S3 Parquet (job Spark multiplex)

### Ambiente PROD — Topologia de Rede

```
┌─── VPC: 172.31.0.0/16 (sa-east-1) ─────────────────────────────┐
│                                                                  │
│  ┌── Subnets Públicas (AZ a, b, c) ──────────────────────────┐  │
│  │  ECS Fargate Tasks (awsvpc, IP público)                    │  │
│  │  ├─ dm-mined-blocks-watcher                                │  │
│  │  ├─ dm-orphan-blocks-watcher                               │  │
│  │  ├─ dm-block-data-crawler                                  │  │
│  │  ├─ dm-mined-txs-crawler (6 réplicas)                      │  │
│  │  ├─ dm-txs-input-decoder                                   │  │
│  │  └─ dm-schema-registry (Cloud Map DNS)                     │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌── Subnets Privadas ───────────────────────────────────────┐  │
│  │  MSK Cluster (2 brokers, AZ a + b)                        │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  S3 VPC Endpoint (gateway) → acesso S3 sem sair da VPC          │
│                                                                  │
│  Security Groups:                                                │
│  ├─ sg-ecs-tasks: permite saída geral, entrada entre tasks      │
│  └─ sg-msk: porta 9098 (SASL/IAM) de sg-ecs-tasks              │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌─── Databricks Workspace ─────────────────────────────────────────┐
│  Unity Catalog: dd_chain_explorer                                │
│  Cluster: 1 worker, LTS Spark, auto-terminate 60 min            │
│  External Locations: raw S3, lakehouse S3, databricks S3         │
│  VPC Peering com VPC principal (para acesso ao MSK)              │
└──────────────────────────────────────────────────────────────────┘
```

**Recursos Terraform (PROD)**:
- **0_remote_state**: S3 backend + DynamoDB lock
- **1_vpc**: VPC, subnets, IGW, security groups, S3 endpoint
- **2_iam**: Roles para ECS (execution + task), Databricks (cross-account + cluster)
- **3_msk**: Cluster MSK (Kafka 3.6.0, 2 brokers, KMS, CloudWatch logs)
- **4_s3**: 3 buckets (raw, lakehouse, databricks) com lifecycle rules
- **6_ecs**: Cluster Fargate + 6 task definitions + services + Cloud Map
- **7_databricks**: Workspace MWS, Unity Catalog, metastore, external locations, cluster
- **9_dynamodb**: Tabela DynamoDB single-table (PK/SK, TTL, PITR, SSE)
- **10_lambda**: Lambda gold_to_dynamodb (S3 event → DynamoDB sync)

### Segurança

| Aspecto | DEV | PROD |
|---------|-----|------|
| **Kafka Auth** | Sem autenticação (rede local) | SASL/OAUTHBEARER com IAM (MSK IAM auth, porta 9098) — tokens gerados pelo ECS task role via `aws-msk-iam-sasl-signer` |
| **Kafka Encryption** | Plaintext | TLS in-transit (SASL_SSL), encryption at-rest (KMS) |
| **DynamoDB** | Credenciais ~/.aws (perfil padrão) | IAM task role (ECS Fargate) |
| **API Keys** | SSM Parameter Store (AWS) | SSM Parameter Store (AWS) — compartilhado |
| **Databricks** | Personal Access Token (PAT) | Service Principal (OAuth M2M) |
| **ECS** | N/A | IAM roles (task execution + task role) |

---

## Referências de Arquivos

| Escopo | Arquivos |
|--------|----------|
| Jobs Streaming | `docker/onchain-stream-txs/src/1_*.py` a `5_*.py` |
| Jobs Batch | `docker/onchain-batch-txs/src/` |
| Spark Streaming | `docker/spark-stream-txs/src/` |
| Docker Compose DEV | `services/dev/compose/local_services.yml`, `app_services.yml`, `batch_services.yml`, `airflow_services.yml` |
| Docker Compose PRD | `services/prd/compose/airflow_services.yml`, `app_services.yml` |
| Terraform DEV | `services/dev/terraform/` (s3.tf, 1_databricks/, 2_s3/, 3_iam/) |
| Terraform PRD | `services/prd/terraform/` (0..8 módulos) |
| DABs | `dabs/databricks.yml`, `dabs/resources/`, `dabs/src/` |
| Airflow DAGs | `mnt/airflow/dags/` |
| CI/CD | `.github/workflows/` |
| Makefile | `Makefile` |
| Configs Compose | `services/dev/compose/conf/` |

---

## TODOs — Arquitetura

- [x] **TODO-A02**: ~~Resolver a ponte Kafka → S3 em PROD.~~ Consolidado no **TODO-A11**.
- [ ] **TODO-A03**: Definir estratégia de Airflow em PROD. Atualmente roda como Docker Compose local. Opções: (a) AWS MWAA (Managed Airflow); (b) ECS Fargate com imagem customizada; (c) Docker Swarm na mesma EC2/instância.
- [ ] **TODO-A04**: Implementar TLS para comunicação Kafka em PROD. Atualmente usa plaintext dentro da VPC. Avaliar se o isolamento via security groups é suficiente ou se precisamos de SASL/TLS.
- [ ] **TODO-A06**: Implementar observabilidade em PROD. Em DEV usamos Control Center para monitorar Kafka. Em PROD precisamos de dashboards CloudWatch e/ou Prometheus+Grafana.
- [ ] **TODO-A07**: Avaliar necessidade de NAT Gateway na VPC de PROD. Atualmente ECS tasks têm IP público para acesso à internet (APIs Web3). NAT Gateway é mais seguro, porém tem custo.
- [ ] **TODO-A10**: Criar ambiente de staging/homologação. Atualmente temos apenas DEV e PROD. Um ambiente intermediário permitiria validar mudanças antes do deploy em produção.
- [ ] **TODO-A11**: Substituir o Spark Streaming Kafka→S3 (DEV-only, `docker/spark-stream-txs/`) por **Kafka Connect com S3 Sink Connector**. O novo componente deve funcionar tanto em DEV quanto em PROD, eliminando a assimetria atual onde DEV usa Spark e PROD não tem ponte Kafka→S3. Consolida os antigos TODO-A02 e TODO-C07.
- [ ] **TODO-A12**: Estudo de custo **ECS Fargate vs EC2**. Duplicar os services de streaming em um cluster EC2 (capacity provider), rodar ambos por 24h e comparar custos. Workload previsível (5 jobs + 6 réplicas do job 4) favorece EC2 com instâncias reservadas.
