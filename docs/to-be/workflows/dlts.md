# Delta Live Tables (DLTs)

## Visão Geral

Os pipelines Delta Live Tables são a camada de processamento streaming do projeto. Cada pipeline roda em modo **contínuo** dentro do workspace Databricks, consumindo dados do Kafka (via Bronze) e transformando-os nas camadas Silver.

Os pipelines são definidos em `dabs/resources/dlt/` e os notebooks em `dabs/src/streaming/`.

---

## Pipelines Deployados

| Pipeline (nome em PROD) | Arquivo YAML | Notebook | Source → Target |
|------------------------|-------------|---------|-----------------|
| `[prod] dm-bronze-multiplex` | `pipeline_bronze_multiplex.yml` | `2_pipeline_bronze_multiplex.py` | Kafka → `b_fast.kafka_topics_multiplexed` |
| `[prod] dm-silver-apps-logs` | `pipeline_silver_layers.yml` | `3_pipeline_silver_apps_logs.py` | Bronze → `s_logs.apps_logs_fast` |
| `[prod] dm-silver-blocks-events` | `pipeline_silver_layers.yml` | `4_pipeline_silver_blocks_events.py` | Bronze → `s_apps.mined_blocks_events` |
| `[prod] dm-silver-blocks` | `pipeline_silver_layers.yml` | `5_pipeline_silver_blocks.py` | Bronze → `s_apps.blocks_fast` |
| `[prod] dm-silver-transactions` | `pipeline_silver_layers.yml` | `6_pipeline_silver_transactions.py` | Bronze → `s_apps.transactions_fast` |

Em DEV, o prefixo é `[dev]` e os pipelines usam o catálogo `dd_chain_explorer_dev`.

---

## Detalhes por Pipeline

### `dm-bronze-multiplex`

**Catalog:** `${var.catalog}` | **Target schema:** `b_fast`  
**Workers:** 1 | **Contínuo:** sim

Lê todos os 5 tópicos Kafka usando IAM auth no MSK:

```python
# Configuração de acesso ao MSK
spark.readStream \
  .format("kafka") \
  .option("kafka.bootstrap.servers", kafka_bootstrap_servers) \
  .option("kafka.security.protocol", "SASL_SSL") \
  .option("kafka.sasl.mechanism", "AWS_MSK_IAM") \
  .option("subscribe", "mainnet.0.application.logs,mainnet.1.mined_blocks.events,mainnet.2.blocks.data,mainnet.3.block.txs.hash_id,mainnet.4.transactions.data")
```

Persiste os dados crus (key + value como string) em `b_fast.kafka_topics_multiplexed` particionado por `topic_name`.

---

### `dm-silver-apps-logs`

**Catalog:** `${var.catalog}` | **Target schema:** `s_logs`  
**Workers:** 1 | **Contínuo:** sim

Filtra `topic_name = 'mainnet.0.application.logs'` da tabela Bronze e deserializa o JSON do campo `value` para a estrutura tipada de logs.

---

### `dm-silver-blocks-events`

**Catalog:** `${var.catalog}` | **Target schema:** `s_apps`  
**Workers:** 1 | **Contínuo:** sim

Filtra `topic_name = 'mainnet.1.mined_blocks.events'` da tabela Bronze. Deserializa o campo `value` para a estrutura `mined_blocks_events`.

---

### `dm-silver-blocks`

**Catalog:** `${var.catalog}` | **Target schema:** `s_apps`  
**Workers:** 1 | **Contínuo:** sim

Filtra `topic_name = 'mainnet.2.blocks.data'` da tabela Bronze. Deserializa o JSON com os dados completos do bloco Ethereum.

---

### `dm-silver-transactions`

**Catalog:** `${var.catalog}` | **Target schema:** `s_apps`  
**Workers:** 2 | **Contínuo:** sim

Filtra `topic_name = 'mainnet.4.transactions.data'` da tabela Bronze. Este pipeline usa 2 workers por ter o maior volume de dados (todas as transações de cada bloco).

---

## Configuração do Bundle (databricks.yml)

Os pipelines recebem as seguintes variáveis do bundle:

| Variável | DEV default | PROD |
|----------|-------------|------|
| `catalog` | `dd_chain_explorer_dev` | `dd_chain_explorer` |
| `kafka_bootstrap_servers` | `localhost:9092` | Endereços MSK (via secret) |

---

## Operações Comuns

### Deploy

```bash
# DEV
make dabs_deploy_dev

# PROD (via CI/CD no merge para main)
# Ou manualmente:
make dabs_deploy_prod
```

### Verificar pipelines deployados

```bash
# Listar via CLI
databricks pipelines list

# Status do bundle
make dabs_status_dev
```

### Full Refresh (reprocessar desde o início)

Use quando for necessário reprocessar todos os dados (ex: após schema change):

```bash
# Via CLI
databricks pipelines start --pipeline-id <id> --full-refresh
```

Ou pelo Databricks UI: **Delta Live Tables → Pipeline → Start → Full Refresh**

### Modo development vs production

Em DEV (`bundle.target == 'dev'`), o campo `development: true` é injetado automaticamente no pipeline. Isso garante isolamento dos dados de DEV e PROD.

---

## Documentação Detalhada

Para a documentação completa dos schemas de cada tabela produzida, fluxo de dados e configuração, consulte [data_processing_stream.md](../application/data_processing_stream.md).
