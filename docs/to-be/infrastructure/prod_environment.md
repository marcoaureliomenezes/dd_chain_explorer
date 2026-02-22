# Ambiente de Produção (PROD)

## Visão Geral da Arquitetura

O ambiente de produção é inteiramente provisionado na AWS (região `sa-east-1`) via Terraform, com o Databricks hospedado dentro da própria VPC AWS. As aplicações Python de captura de dados rodam em ECS Fargate, o Kafka é gerenciado pelo Amazon MSK, e todo o processamento de dados é feito no Databricks via Delta Live Tables e Workflows.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ AWS sa-east-1                                                                │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ VPC dm-chain-explorer                                                    ││
│  │                                                                          ││
│  │  ┌─────────────────┐    Kafka (IAM)    ┌──────────────────────────────┐ ││
│  │  │  ECS Fargate     │ ───────────────▶ │  MSK (2 brokers, t3.small)  │ ││
│  │  │                  │                  │  Glue Schema Registry         │ ││
│  │  │  · mined-blocks  │                  └──────────────┬───────────────┘ ││
│  │  │  · orphan-blocks │                                 │                 ││
│  │  │  · block-crawler │          DynamoDB               │ Kafka           ││
│  │  │  · txs-crawler   │ ───────▶ (3 tabelas)            │                 ││
│  │  └─────────────────┘                                  ▼                 ││
│  │                                        ┌──────────────────────────────┐ ││
│  │                                        │  Databricks Workspace        │ ││
│  │  ┌─────────────────┐                  │  (dentro da VPC via peering) │ ││
│  │  │  S3              │ ◀──────────────  │                              │ ││
│  │  │  · raw-data      │                  │  DLT Pipelines (streaming)   │ ││
│  │  │  · lakehouse     │ ◀──────────────  │  Workflows Batch             │ ││
│  │  └─────────────────┘                  └──────────────────────────────┘ ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Terraform — Módulos de Infraestrutura

Todos os módulos usam **backend S3 remoto** para estado compartilhado e lock via DynamoDB.

| Bucket de estado | `dm-chain-explorer-terraform-state` |
|---|---|
| Tabela de lock | `dm-chain-explorer-terraform-lock` |
| Região | `sa-east-1` |
| Versão Terraform | `>= 1.3.0` |

### Dependências entre módulos

```
0_remote_state (cria bucket + lock table)
  └── 1_vpc
        ├── 2_iam     (depende de vpc, s3)
        ├── 3_msk     (depende de vpc)
        ├── 4_s3
        ├── 5_dynamodb
        ├── 6_ecs     (depende de vpc, iam, msk, dynamodb)
        └── 7_databricks (depende de vpc, iam, s3)
```

---

### Módulo 0 — Remote State (`0_remote_state`)

Cria os recursos de backend para os demais módulos. Aplicado uma única vez com backend local.

| Recurso | Nome |
|---------|------|
| S3 Bucket | `dm-chain-explorer-terraform-state` |
| DynamoDB Table (lock) | `dm-chain-explorer-terraform-lock` |

---

### Módulo 1 — VPC (`1_vpc`)

Cria a rede privada que conecta todos os serviços.

| Recurso | Detalhe |
|---------|---------|
| VPC | CIDR: `10.0.0.0/16` |
| Subnets privadas | Pelo menos 2 AZs (para MSK e ECS) |
| NAT Gateway | Acesso à internet para ECS (chamadas às APIs blockchain) |
| Security Groups | `sg_ecs_tasks`, `sg_msk`, `sg_databricks` |

---

### Módulo 2 — IAM (`2_iam`)

Policies e roles para autenticação sem credenciais estáticas.

| Role | Usado por | Permissões principais |
|------|-----------|----------------------|
| `ecs_task_execution_role` | ECS (pull de imagem, CloudWatch) | `ecr:*`, `logs:*`, `secretsmanager:GetSecretValue` |
| `ecs_task_role` | Contêineres ECS em runtime | `msk:Connect`, `msk:WriteData`, `msk:ReadData`, `dynamodb:*` (tabelas dm-api-*), `s3:PutObject` (bucket raw) |
| `databricks_cross_account_role` | Workspace Databricks | `ec2:*` (VPC peering), `sts:AssumeRole` |

---

### Módulo 3 — MSK (`3_msk`)

Cluster Kafka gerenciado pela AWS.

| Parâmetro | Valor |
|-----------|-------|
| Nome | `dm-chain-explorer-msk` |
| Kafka version | Variável `kafka_version` (ex: `3.5.x`) |
| Brokers | 2 (1 por AZ) |
| Tipo de instância | `kafka.t3.small` |
| Armazenamento | Variável `broker_ebs_size_gb` |
| Autenticação | IAM (SASL/IAM) — sem usuário/senha |
| Criptografia em trânsito | `TLS_PLAINTEXT` |
| Criptografia em repouso | KMS gerenciado |
| Partições padrão | `8` |
| Replicação | `2` |
| Retenção de logs | `168h` (7 dias) |
| Schema Registry | AWS Glue Schema Registry (`dm-chain-explorer-schema-registry`) |
| Logs de broker | CloudWatch `/aws/msk/dm-chain-explorer/broker-logs` (7 dias) |

#### Tópicos Kafka

| Tópico | Partições | Produtores | Consumidores |
|--------|-----------|-----------|-------------|
| `mainnet.0.application.logs` | 8 | Todos os apps | DLT Silver Logs |
| `mainnet.1.mined_blocks.events` | 8 | `mined-blocks-watcher` | `block-data-crawler`, DLT |
| `mainnet.2.blocks.data` | 8 | `block-data-crawler` | DLT Bronze, Silver Blocks |
| `mainnet.3.block.txs.hash_id` | 8 | `block-data-crawler` | `mined-txs-crawler` |
| `mainnet.4.transactions.data` | 8 | `mined-txs-crawler` | DLT Bronze, Silver Txs |

---

### Módulo 4 — S3 (`4_s3`)

Dois buckets S3 para armazenamento de dados.

| Bucket | Propósito | Acesso |
|--------|-----------|--------|
| `dm-chain-explorer-raw-data` | Landing zone de dados brutos (transações históricas via Etherscan) | ECS task role, Databricks |
| `dm-chain-explorer-lakehouse` | Lakehouse Delta (tabelas Bronze/Silver/Gold) | Databricks workspace |

---

### Módulo 5 — DynamoDB (`5_dynamodb`)

Três tabelas para o sistema de gerenciamento de chaves de API (substitui Redis do AS-IS).

| Tabela | Hash Key | Sort Key | TTL | Propósito |
|--------|----------|----------|-----|-----------|
| `dm-api-key-semaphore` | `api_key_name` (S) | — | — | Semáforo: qual processo detém qual chave |
| `dm-api-key-consumption` | `api_key_name` (S) | `date` (S) | `expire_at` | Contagem diária de chamadas por chave |
| `dm-popular-contracts` | `contract_address` (S) | — | — | Cache dos contratos mais transacionados |

Todas usam `billing_mode: PAY_PER_REQUEST` (sem provisionamento de capacidade).

---

### Módulo 6 — ECS (`6_ecs`)

Cluster ECS Fargate para as aplicações Python de captura on-chain.

**Cluster:** `dm-chain-explorer-ecs` (Container Insights: habilitado)  
**Logs:** CloudWatch `/ecs/dm-chain-explorer` (7 dias)

#### Task Definitions e Serviços

| Serviço | Script | CPU | Memória | Réplicas | Tópicos produzidos |
|---------|--------|-----|---------|----------|--------------------|
| `dm-mined-blocks-watcher` | `1_mined_blocks_watcher.py` | 256 | 512 MB | 1 | `mainnet.1.mined_blocks.events` |
| `dm-orphan-blocks-watcher` | `2_orphan_blocks_watcher.py` | 256 | 512 MB | 1 | `mainnet.1.mined_blocks.events` (monitor) |
| `dm-block-data-crawler` | `3_block_data_crawler.py` | 512 | 1024 MB | 1 | `mainnet.2.blocks.data`, `mainnet.3.block.txs.hash_id` |
| `dm-mined-txs-crawler` | `4_mined_txs_crawler.py` | 512 | 1024 MB | **8** | `mainnet.4.transactions.data` |

Todos os serviços:
- Rodam em subnets **privadas** (sem IP público)
- Acessam MSK via IAM (sem credenciais em variáveis de ambiente)
- Logs via CloudWatch (`awslogs` driver)

> O `mined-txs-crawler` roda com **8 réplicas** para paralelizar a busca de dados das transações via API blockchain.

---

### Módulo 7 — Databricks (`7_databricks`)

Workspace Databricks on AWS criado dentro da VPC do projeto.

| Parâmetro | Valor |
|-----------|-------|
| Provider | `databricks/databricks >= 1.36.0` |
| Tipo | Workspace AWS (não Azure) |
| Autenticação | Service principal OAuth (account-level) |
| Integração VPC | VPC peering com `dm-chain-explorer` |
| Credential | Cross-account role do módulo 2 |
| Unity Catalog | Habilitado — catalog: `dd_chain_explorer` |

---

## Databricks Asset Bundles (DABs) — PROD

Os recursos Databricks não são gerenciados pelo Terraform depois da criação do workspace. O deploy de pipelines, workflows e notebooks é feito via **Databricks Asset Bundles (DABs)** com a CLI.

O bundle está em `dabs/` e é deployado no target `prod` pelo CI/CD.

Recursos deployados em PROD:

| Tipo | Nome | Descrição |
|------|------|-----------|
| DLT Pipeline | `dm-bronze-multiplex` | Ingestão de todos os tópicos → Bronze |
| DLT Pipeline | `dm-silver-apps-logs` | Bronze → Silver de logs |
| DLT Pipeline | `dm-silver-blocks-events` | Bronze → Silver de eventos de blocos |
| DLT Pipeline | `dm-silver-blocks` | Bronze → Silver de dados completos de blocos |
| DLT Pipeline | `dm-silver-transactions` | Bronze → Silver de transações |
| Workflow | `dm-ddl-setup` | Setup inicial: cria todos os schemas e tabelas |
| Workflow | `dm-periodic-processing` | A cada 6h: identifica contratos populares + ingere histórico |
| Workflow | `dm-iceberg-maintenance` | Diário às 2h: OPTIMIZE + VACUUM + monitor |
| Workflow | `dm-teardown` | Teardown do ambiente (DEV only) |

Consulte as documentações detalhadas:
- [DLT Pipelines](../workflows/dlts.md)
- [Workflows Batch](../workflows/jobs.md)
- [Processamento Streaming](../application/data_processing_stream.md)
- [Processamento Batch](../application/data_processing_batch.md)

---

## Unity Catalog — Organização de Namespaces

```
catalog: dd_chain_explorer (PROD) / dd_chain_explorer_dev (DEV)
├── b_fast
│   └── kafka_topics_multiplexed     ← landing zone de todos os tópicos Kafka
├── bronze
│   └── popular_contracts_txs        ← transações históricas de contratos populares
├── s_apps                           ← Silver: dados de aplicação
│   ├── mined_blocks_events
│   ├── blocks_fast
│   └── transactions_fast
├── s_logs                           ← Silver: logs das aplicações
│   └── apps_logs_fast
└── gold                             ← Views analíticas
    ├── blocks_with_tx_count
    ├── top_contracts_by_volume
    └── blocks_hourly_summary
```

---

## Diagrama de Fluxo de Dados

```
Blockchain (Ethereum Mainnet)
        │
        ▼
┌───────────────┐     ┌──────────────────┐
│ mined-blocks  │────▶│ mainnet.1.mined   │
│  -watcher     │     │  _blocks.events   │
└───────────────┘     └───────┬──────────┘
                              │
                              ▼
┌───────────────┐     ┌──────────────────┐     ┌──────────────────────┐
│ block-data    │────▶│ mainnet.2.blocks  │────▶│ DLT: Bronze →        │
│  -crawler     │     │  .data            │     │ Silver Blocks        │
│               │     ├──────────────────┤     └──────────────────────┘
│               │────▶│ mainnet.3.block   │
│               │     │  .txs.hash_id     │
└───────────────┘     └───────┬──────────┘
                              │
                              ▼
┌───────────────┐     ┌──────────────────┐     ┌──────────────────────┐
│ mined-txs     │────▶│ mainnet.4.txs    │────▶│ DLT: Bronze →        │
│  -crawler     │     │  .data            │     │ Silver Txs           │
│ (8 réplicas)  │     └──────────────────┘     └──────────────────────┘
└───────────────┘
        │ DynamoDB (semáforo de API keys)
        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Databricks: Bronze (b_fast.kafka_topics_multiplexed)                    │
│    └── Silver: s_apps.blocks_fast                                       │
│    └── Silver: s_apps.transactions_fast                                 │
│    └── Silver: s_apps.mined_blocks_events                               │
│    └── Silver: s_logs.apps_logs_fast                                    │
│         └── Gold: views analíticas                                      │
└─────────────────────────────────────────────────────────────────────────┘
```
