# Databricks notebook source
# MAGIC %md
# MAGIC # Ethereum DLT Pipeline — Bronze + Silver + Gold
# MAGIC
# MAGIC Pipeline unificado com três camadas:
# MAGIC
# MAGIC ## Bronze — `b_ethereum`
# MAGIC - `kafka_topics_multiplexed`: ingestão de todos os tópicos Kafka
# MAGIC   - **PROD** (`source.type = kafka`): Kafka MSK via IAM auth (streaming)
# MAGIC   - **DEV**  (`source.type = s3`):   Auto Loader sobre Parquet no S3
# MAGIC
# MAGIC ## Silver — `s_apps`
# MAGIC Lê da bronze via `dlt.read()` (interno ao pipeline, sem dependência externa):
# MAGIC - `s_apps.mined_blocks_events`          ← `mainnet.1.mined_blocks.events`
# MAGIC - `s_apps.blocks_fast`                  ← `mainnet.2.blocks.data`
# MAGIC - `s_apps.transaction_hash_ids`         ← `mainnet.3.block.txs.hash_id`
# MAGIC - `s_apps.transactions_fast`            ← `mainnet.4.transactions.data` (raw, sem decoded)
# MAGIC - `s_apps.txs_inputs_decoded_fast`      ← `mainnet.5.transactions.input_decoded`
# MAGIC - `s_apps.transactions_ethereum`        ← JOIN transactions_fast + txs_inputs_decoded_fast + blocks_fast
# MAGIC - `s_apps.blocks_withdrawals`           ← blocks_fast.withdrawals explodido (1 linha por saque Beacon Chain)
# MAGIC
# MAGIC ## Gold — `s_apps` (Materialized Views)
# MAGIC - `s_apps.popular_contracts_ranking` ← top 100 contratos por volume de txs na última hora
# MAGIC - `s_apps.peer_to_peer_txs`          ← transações EOA→EOA (input vazio/nulo)
# MAGIC - `s_apps.ethereum_gas_consume`      ← consumo de gas por transação com tipo classificado
# MAGIC - `s_apps.transactions_lambda`       ← visão unificada streaming + batch com input decodificado

# COMMAND ----------

import dlt
from pyspark.sql import functions as F
from pyspark.sql.types import StringType
from pyspark.sql.avro.functions import from_avro
from pyspark.sql.window import Window


# ── Configuration ─────────────────────────────────────────────────────────────

SOURCE_TYPE     = spark.conf.get("source.type", "kafka")       # "kafka" or "s3"
KAFKA_BOOTSTRAP = spark.conf.get("kafka.bootstrap.servers", "")
MSK_IAM_AUTH    = spark.conf.get("kafka.msk.iam.auth", "false").lower() == "true"
S3_PATH         = spark.conf.get("s3.ingestion.path", "")

TOPICS = [
    "mainnet.0.application.logs",
    "mainnet.1.mined_blocks.events",
    "mainnet.2.blocks.data",
    "mainnet.3.block.txs.hash_id",
    "mainnet.4.transactions.data",
    "mainnet.5.transactions.input_decoded",
]

# Catalog e S3 bucket para Materialized Views que exportam dados
CATALOG         = spark.conf.get("catalog", "dev")
S3_EXPORT_PATH  = spark.conf.get("s3.export.path", "")


# ════════════════════════════════════════════════════════════════════════════
# BRONZE LAYER
# ════════════════════════════════════════════════════════════════════════════

# COMMAND ----------
# MAGIC %md
# MAGIC ## Bronze — `kafka_topics_multiplexed`

# COMMAND ----------

# ── Kafka source (PROD) ──────────────────────────────────────────────────────

def _kafka_reader(topic: str):
    """Retorna um Spark Streaming reader para um tópico Kafka específico."""
    options = {
        "kafka.bootstrap.servers": KAFKA_BOOTSTRAP,
        "subscribe": topic,
        "startingOffsets": "latest",
        "failOnDataLoss": "false",
    }
    if MSK_IAM_AUTH:
        options.update({
            "kafka.security.protocol": "SASL_SSL",
            "kafka.sasl.mechanism": "AWS_MSK_IAM",
            "kafka.sasl.jaas.config": (
                "software.amazon.msk.auth.iam.IAMLoginModule required;"
            ),
            "kafka.sasl.client.callback.handler.class": (
                "software.amazon.msk.auth.iam.IAMClientCallbackHandler"
            ),
        })
    return spark.readStream.format("kafka").options(**options)


def _read_from_kafka():
    """Lê todos os tópicos Kafka e retorna um DataFrame unificado (streaming)."""
    from functools import reduce
    dfs = []
    for topic in TOPICS:
        df = (
            _kafka_reader(topic)
            .load()
            .select(
                F.lit(topic).alias("topic_name"),
                F.col("partition").alias("kafka_partition"),
                F.col("offset").alias("kafka_offset"),
                F.col("timestamp").alias("kafka_timestamp"),
                F.col("key").cast(StringType()).alias("key"),
                F.col("value"),
            )
        )
        dfs.append(df)
    return reduce(lambda a, b: a.union(b), dfs)


# ── S3 Parquet source (DEV) ──────────────────────────────────────────────────

def _read_from_s3():
    """
    Lê dados Parquet do S3 via Auto Loader (cloudFiles).
    Estrutura esperada: s3://<bucket>/bronze/kafka_multiplex/topic_name=<topic>/...parquet
    """
    return (
        spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", "parquet")
        .option("cloudFiles.schemaLocation", f"{S3_PATH}/_schema")
        .option("cloudFiles.inferColumnTypes", "true")
        .load(S3_PATH)
        .select(
            F.col("topic_name"),
            F.col("kafka_partition"),
            F.col("kafka_offset"),
            F.col("kafka_timestamp"),
            F.col("key"),
            F.col("value"),
        )
    )


# ── DLT Bronze table ─────────────────────────────────────────────────────────

@dlt.table(
    name="kafka_topics_multiplexed",
    comment="Bronze: todos os tópicos Kafka multiplexados em uma única tabela",
    table_properties={
        "quality": "bronze",
        "pipelines.autoOptimize.managed": "true",
    },
    partition_cols=["topic_name"],
)
def bronze_multiplex():
    """Source dinâmico: Kafka (PROD) ou S3 Auto Loader (DEV)."""
    if SOURCE_TYPE == "s3":
        return _read_from_s3()
    return _read_from_kafka()


# ════════════════════════════════════════════════════════════════════════════
# SILVER LAYER
# Lê da bronze via dlt.read() — referência interna ao pipeline.
# Tabelas escritas em schemas s_apps / s_logs via name="schema.table".
# ════════════════════════════════════════════════════════════════════════════

# COMMAND ----------
from _avro_schemas import *  # noqa: F401,F403  (defined as DLT file library)

# COMMAND ----------


# ── Helper: lê bronze interna ao pipeline + deserializa Avro ─────────────────

def _silver_avro(topic: str, avro_schema: str):
    """
    Lê da tabela bronze via dlt.read() (referência interna ao pipeline),
    filtra pelo tópico, remove o header Confluent (5 bytes) e desserializa o
    payload Avro usando o schema embutido.

    Retorna DataFrame com coluna `parsed` (struct) + metadados Kafka.
    """
    return (
        dlt.read("kafka_topics_multiplexed")
        .filter(F.col("topic_name") == topic)
        .withColumn("avro_payload", F.expr("substring(value, 6)"))
        .withColumn("parsed", from_avro(F.col("avro_payload"), avro_schema))
    )


# COMMAND ----------
# MAGIC %md
# MAGIC ## Silver 1 — Mined Blocks Events → `s_apps.mined_blocks_events`

# COMMAND ----------

@dlt.table(
    name="s_apps.mined_blocks_events",
    comment="Silver: eventos de blocos minerados na Ethereum Mainnet",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
    },
)
@dlt.expect_or_drop("valid_block_number", "block_number IS NOT NULL")
@dlt.expect_or_drop("valid_block_hash",   "block_hash IS NOT NULL")
def silver_mined_blocks_events():
    df = _silver_avro("mainnet.1.mined_blocks.events", AVRO_SCHEMA_MINED_BLOCKS_EVENTS)
    return df.select(
        F.col("parsed.block_number").alias("block_number"),
        F.col("parsed.block_hash").alias("block_hash"),
        F.col("parsed.block_timestamp").alias("block_timestamp"),
        F.to_timestamp(F.col("parsed.block_timestamp")).alias("event_time"),
        F.col("kafka_timestamp"),
        F.col("kafka_partition"),
        F.col("kafka_offset"),
    )


# COMMAND ----------
# MAGIC %md
# MAGIC ## Silver 2 — Blocks Data → `s_apps.blocks_fast`

# COMMAND ----------

@dlt.table(
    name="s_apps.blocks_fast",
    comment="Silver: dados completos dos blocos Ethereum (header + withdrawals)",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
    },
)
@dlt.expect_or_drop("valid_block_number", "block_number IS NOT NULL")
@dlt.expect_or_drop("valid_hash",         "block_hash IS NOT NULL")
def silver_blocks_fast():
    df = _silver_avro("mainnet.2.blocks.data", AVRO_SCHEMA_BLOCKS)
    return df.select(
        F.col("parsed.number").alias("block_number"),
        F.col("parsed.hash").alias("block_hash"),
        F.col("parsed.parentHash").alias("parent_hash"),
        F.to_timestamp(F.col("parsed.timestamp")).alias("block_time"),
        F.col("parsed.timestamp").alias("block_timestamp"),
        F.col("parsed.miner").alias("miner"),
        F.col("parsed.difficulty").alias("difficulty"),
        F.col("parsed.totalDifficulty").alias("total_difficulty"),
        F.col("parsed.nonce").alias("nonce"),
        F.col("parsed.size").alias("size"),
        F.col("parsed.baseFeePerGas").alias("base_fee_per_gas"),
        F.col("parsed.gasLimit").alias("gas_limit"),
        F.col("parsed.gasUsed").alias("gas_used"),
        F.col("parsed.logsBloom").alias("logs_bloom"),
        F.col("parsed.extraData").alias("extra_data"),
        F.col("parsed.transactionsRoot").alias("transactions_root"),
        F.col("parsed.stateRoot").alias("state_root"),
        F.size(F.col("parsed.transactions")).alias("transaction_count"),
        F.col("parsed.transactions").alias("transactions"),
        F.col("parsed.withdrawals").alias("withdrawals"),
        F.col("kafka_timestamp"),
        F.col("kafka_partition"),
        F.col("kafka_offset"),
    )


# COMMAND ----------
# MAGIC %md
# MAGIC ## Silver 3 — Transaction Hash IDs → `s_apps.transaction_hash_ids`

# COMMAND ----------

@dlt.table(
    name="s_apps.transaction_hash_ids",
    comment="Silver: hash IDs de transações por bloco",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
    },
)
@dlt.expect_or_drop("valid_tx_hash", "tx_hash IS NOT NULL")
def silver_transaction_hash_ids():
    df = _silver_avro("mainnet.3.block.txs.hash_id", AVRO_SCHEMA_TX_HASH_IDS)
    return df.select(
        F.col("parsed.tx_hash").alias("tx_hash"),
        F.col("key").alias("block_hash"),
        F.col("kafka_timestamp"),
        F.col("kafka_partition"),
        F.col("kafka_offset"),
    )


# COMMAND ----------
# MAGIC %md
# MAGIC ## Silver 4 — Transactions raw → `s_apps.transactions_fast`
# MAGIC Contém apenas os dados brutos do tópico `mainnet.4.transactions.data`.
# MAGIC **Sem** campos decoded (method/parms/decode_type) — esses ficam em `txs_inputs_decoded_fast`.

# COMMAND ----------

@dlt.table(
    name="s_apps.transactions_fast",
    comment="Silver: transações Ethereum do tópico mainnet.4.transactions.data — dados raw sem input decodificado",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
    },
    partition_cols=["event_date"],
)
@dlt.expect_or_drop("valid_hash",       "tx_hash IS NOT NULL")
@dlt.expect_or_drop("valid_block",      "block_number IS NOT NULL")
@dlt.expect("valid_from_address", "from_address RLIKE '^0x[a-fA-F0-9]{40}$'")
@dlt.expect("valid_to_address",   "to_address IS NULL OR to_address RLIKE '^0x[a-fA-F0-9]{40}$'")
def silver_transactions_fast():
    df = _silver_avro("mainnet.4.transactions.data", AVRO_SCHEMA_TRANSACTIONS)
    return df.select(
        F.col("parsed.hash").alias("tx_hash"),
        F.col("parsed.blockNumber").alias("block_number"),
        F.col("parsed.blockHash").alias("block_hash"),
        F.col("parsed.transactionIndex").alias("transaction_index"),
        F.col("parsed.`from`").alias("from_address"),
        F.col("parsed.to").alias("to_address"),
        F.col("parsed.value").alias("value"),
        F.col("parsed.input").alias("input"),
        F.col("parsed.gas").alias("gas"),
        F.col("parsed.gasPrice").alias("gas_price"),
        F.col("parsed.nonce").alias("nonce"),
        F.col("parsed.v").alias("v"),
        F.col("parsed.r").alias("r"),
        F.col("parsed.s").alias("s"),
        F.col("parsed.type").alias("tx_type"),
        F.col("parsed.accessList").alias("access_list"),
        F.col("kafka_timestamp"),
        F.col("kafka_partition"),
        F.col("kafka_offset"),
        F.to_date(F.col("kafka_timestamp")).alias("event_date"),
    )


# COMMAND ----------
# MAGIC %md
# MAGIC ## Silver 5 — Decoded inputs → `s_apps.txs_inputs_decoded_fast`
# MAGIC Dados do tópico `mainnet.5.transactions.input_decoded`: method, parms, decode_type.

# COMMAND ----------

@dlt.table(
    name="s_apps.txs_inputs_decoded_fast",
    comment="Silver: inputs de transações decodificados — topic mainnet.5.transactions.input_decoded",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
    },
)
@dlt.expect_or_drop("valid_tx_hash", "tx_hash IS NOT NULL")
def silver_txs_inputs_decoded_fast():
    df = _silver_avro("mainnet.5.transactions.input_decoded", AVRO_SCHEMA_INPUT_DECODED)
    return df.select(
        F.col("parsed.tx_hash").alias("tx_hash"),
        F.col("parsed.contract_address").alias("contract_address"),
        F.col("parsed.method").alias("method"),
        F.col("parsed.parms").alias("parms"),
        F.col("parsed.decode_type").alias("decode_type"),
        F.col("kafka_timestamp"),
        F.col("kafka_partition"),
        F.col("kafka_offset"),
    )


# COMMAND ----------
# MAGIC %md
# MAGIC ## Silver 6 — Enriched transactions → `s_apps.transactions_ethereum`
# MAGIC
# MAGIC Stream-Stream JOIN: `transactions_fast` ← `txs_inputs_decoded_fast`
# MAGIC Stream-Static JOIN: resultado ← `blocks_fast` (para tx_timestamp)
# MAGIC
# MAGIC Padrão: Stream-Static JOIN (DLT não suporta Stream-Stream JOIN).
# MAGIC - txs_inputs_decoded_fast lido como snapshot estático (dlt.read)
# MAGIC - blocks_fast lido como batch snapshot (dlt.read) para join stream-static
# MAGIC - Sem necessidade de watermark ou condição de intervalo

# COMMAND ----------

@dlt.table(
    name="s_apps.transactions_ethereum",
    comment=(
        "Silver: transações Ethereum enriquecidas — JOIN streaming com decoded inputs e blocks. "
        "Contém tx_timestamp (do bloco), method/parms/decode_type (do decoder) e campos do bloco."
    ),
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
    },
    partition_cols=["event_date"],
)
@dlt.expect_or_drop("valid_hash",       "tx_hash IS NOT NULL")
@dlt.expect_or_drop("valid_block",      "block_number IS NOT NULL")
@dlt.expect("valid_from_address", "from_address RLIKE '^0x[a-fA-F0-9]{40}$'")
@dlt.expect("valid_to_address",   "to_address IS NULL OR to_address RLIKE '^0x[a-fA-F0-9]{40}$'")
def silver_transactions_ethereum():
    # ── Stream: transações raw ───────────────────────────────────────────────
    # dlt.read_stream → Streaming Table (consume novos registros incrementalmente)
    txs = dlt.read_stream("s_apps.transactions_fast")

    # ── Static: inputs decodificados (snapshot) ──────────────────────────────
    # DLT NÃO suporta Stream-Stream JOIN. Decoded inputs são lidos como
    # snapshot estático (dlt.read) — será atualizado a cada update do pipeline.
    decoded = (
        dlt.read("s_apps.txs_inputs_decoded_fast")
        .select(
            F.col("tx_hash").alias("d_tx_hash"),
            F.col("contract_address"),
            F.col("method"),
            F.col("parms"),
            F.col("decode_type"),
        )
    )

    # ── Stream-Static LEFT JOIN por tx_hash ──────────────────────────────────
    joined = txs.join(decoded, txs["tx_hash"] == decoded["d_tx_hash"], "left")

    # ── Stream-Static JOIN: enriquece com dados do bloco (timestamp + gas) ───
    # dlt.read() retorna snapshot do bloco — suportado como stream-static join.
    blocks = (
        dlt.read("s_apps.blocks_fast")
        .select(
            F.col("block_number").alias("b_block_number"),
            F.from_unixtime("block_timestamp", "yyyy-MM-dd HH:mm:ss").alias("tx_timestamp"),
            F.col("gas_limit").alias("block_gas_limit"),
            F.col("gas_used").alias("block_gas_used"),
            F.col("base_fee_per_gas"),
        )
    )

    return (
        joined
        .join(blocks, joined["block_number"] == blocks["b_block_number"], "left")
        .select(
            # Campos da transação
            F.col("tx_hash"),
            F.col("block_number"),
            F.col("block_hash"),
            F.col("transaction_index"),
            F.col("from_address"),
            F.col("to_address"),
            F.col("value"),
            F.col("input"),
            F.col("gas"),
            F.col("gas_price"),
            F.col("nonce"),
            F.col("tx_type"),
            # Campos do bloco
            F.col("tx_timestamp"),
            F.col("block_gas_limit"),
            F.col("block_gas_used"),
            F.col("base_fee_per_gas"),
            # Campos do decoder (topics 5)
            F.col("contract_address"),
            F.col("method"),
            F.col("parms"),
            F.col("decode_type"),
            # Placeholder para enriquecimento batch Etherscan
            F.lit(None).cast("string").alias("input_etherscan"),
            F.col("kafka_timestamp"),
            F.col("kafka_partition"),
            F.col("kafka_offset"),
            F.to_date(F.col("kafka_timestamp")).alias("event_date"),
        )
    )


# COMMAND ----------
# MAGIC %md
# MAGIC ## Silver 7 — Beacon Chain withdrawals → `s_apps.blocks_withdrawals`
# MAGIC
# MAGIC Explode do campo `withdrawals` de `blocks_fast`: cada validator que sacou
# MAGIC ETH excedente (acima de 32 ETH) gera uma linha. Introduzido no EIP-4895
# MAGIC (Shanghai/Capella, Abril 2023). Máximo de 16 saques por bloco.

# COMMAND ----------

@dlt.table(
    name="s_apps.blocks_withdrawals",
    comment=(
        "Silver: saques ETH da Beacon Chain (EIP-4895) — uma linha por withdrawal por bloco. "
        "Campo amount em Gwei (÷1e9 = ETH)."
    ),
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
    },
)
def silver_blocks_withdrawals():
    return (
        dlt.read_stream("s_apps.blocks_fast")
        .filter(F.col("withdrawals").isNotNull() & (F.size(F.col("withdrawals")) > 0))
        .select(
            F.col("block_number"),
            F.from_unixtime("block_timestamp", "yyyy-MM-dd HH:mm:ss").alias("block_timestamp"),
            F.col("miner"),
            F.col("kafka_timestamp"),
            F.explode("withdrawals").alias("wd"),
        )
        .select(
            F.col("block_number"),
            F.col("block_timestamp"),
            F.col("miner"),
            F.col("wd.index").alias("withdrawal_index"),
            F.col("wd.validatorIndex").alias("validator_index"),
            F.col("wd.address").alias("withdrawal_address"),
            F.col("wd.amount").alias("amount_gwei"),
            (F.col("wd.amount") / F.lit(1e9)).alias("amount_eth"),
            F.col("kafka_timestamp"),
        )
    )


# ════════════════════════════════════════════════════════════════════════════
# GOLD — Materialized Views (atualizadas a cada execução do pipeline)
# ════════════════════════════════════════════════════════════════════════════

# COMMAND ----------
# MAGIC %md
# MAGIC ## Gold 1 — Popular Contracts Ranking → `s_apps.popular_contracts_ranking`
# MAGIC
# MAGIC Top 100 contratos Ethereum com mais transações na última hora.
# MAGIC Serve como fonte para o Job Batch que captura transações históricas.

# COMMAND ----------

@dlt.table(
    name="s_apps.popular_contracts_ranking",
    comment="Gold MV: top 100 contratos mais populares por volume de transações",
    table_properties={
        "quality": "gold",
        "pipelines.autoOptimize.managed": "true",
    },
)
def gold_popular_contracts_ranking():
    """
    Lê de transactions_fast (DLT interna) e calcula ranking dos 100 contratos
    que mais receberam transações. Usa janela de 1 hora a partir do kafka_timestamp.
    """
    df = dlt.read("s_apps.transactions_fast")

    return (
        df
        .filter(F.col("to_address").isNotNull())
        .filter(F.col("kafka_timestamp") >= F.expr("current_timestamp() - INTERVAL 1 HOUR"))
        .groupBy("to_address")
        .agg(
            F.count("*").alias("tx_count"),
            F.max("kafka_timestamp").alias("last_seen"),
            F.min("kafka_timestamp").alias("first_seen"),
            F.countDistinct("from_address").alias("unique_senders"),
        )
        .orderBy(F.desc("tx_count"))
        .limit(100)
        .select(
            F.col("to_address").alias("contract_address"),
            "tx_count",
            "unique_senders",
            "first_seen",
            "last_seen",
            F.current_timestamp().alias("computed_at"),
        )
    )


# COMMAND ----------
# MAGIC %md
# MAGIC ## Gold 2 — Peer-to-Peer transactions → `s_apps.peer_to_peer_txs`
# MAGIC
# MAGIC Transações ETH diretas entre endereços EOA (Externally Owned Accounts).
# MAGIC Identificadas por campo `input` vazio/nulo/"0x" e `to_address` não nulo.

# COMMAND ----------

@dlt.table(
    name="s_apps.peer_to_peer_txs",
    comment="Gold MV: transferências ETH diretas entre endereços EOA (input vazio ou nulo)",
    table_properties={
        "quality": "gold",
        "pipelines.autoOptimize.managed": "true",
    },
)
def gold_peer_to_peer_txs():
    return (
        dlt.read("s_apps.transactions_ethereum")
        .filter(
            F.col("to_address").isNotNull() &
            (
                F.col("input").isNull() |
                (F.col("input") == "") |
                (F.col("input") == "0x")
            )
        )
        .select(
            F.col("tx_hash"),
            F.col("block_number"),
            F.col("from_address"),
            F.col("to_address"),
            F.col("value"),
            F.col("gas"),
            F.col("gas_price"),
            F.col("tx_timestamp"),
            F.col("base_fee_per_gas"),
            F.col("kafka_timestamp"),
        )
    )


# COMMAND ----------
# MAGIC %md
# MAGIC ## Gold 3 — Gas consumption → `s_apps.ethereum_gas_consume`
# MAGIC
# MAGIC Materialized view com consumo de gas por transação e tipo classificado:
# MAGIC - `peer_to_peer`        → input nulo/vazio/"0x" e to_address não nulo
# MAGIC - `contract_deploy`     → to_address nulo e input não vazio (cria contrato)
# MAGIC - `contract_interaction`→ demais (chama função de contrato)

# COMMAND ----------

@dlt.table(
    name="s_apps.ethereum_gas_consume",
    comment="Gold MV: consumo de gas por transação com classificação de tipo (peer_to_peer | contract_interaction | contract_deploy)",
    table_properties={
        "quality": "gold",
        "pipelines.autoOptimize.managed": "true",
    },
)
def gold_ethereum_gas_consume():
    txs = dlt.read("s_apps.transactions_ethereum")

    type_transaction = (
        F.when(
            # Deploy: to é nulo e input não é vazio
            F.col("to_address").isNull() &
            F.col("input").isNotNull() &
            (F.col("input") != "") &
            (F.col("input") != "0x"),
            F.lit("contract_deploy"),
        ).when(
            # Peer-to-peer: input vazio/nulo
            F.col("input").isNull() |
            (F.col("input") == "") |
            (F.col("input") == "0x"),
            F.lit("peer_to_peer"),
        ).otherwise(
            F.lit("contract_interaction"),
        )
    )

    # Porcentagem de gas que esta tx consumiu no bloco.
    # Nota: `gas` aqui é o gas limit da tx (o Avro de streaming não carrega
    # gas_used do receipt). block_gas_used é o total efetivo do bloco.
    gas_pct_of_block = (
        F.when(
            F.col("block_gas_used").isNotNull() & (F.col("block_gas_used") > 0),
            F.round(F.col("gas").cast("double") / F.col("block_gas_used") * 100, 4),
        ).otherwise(F.lit(None).cast("double"))
    )

    return txs.select(
        F.col("block_number"),
        F.col("tx_hash"),
        F.col("from_address"),
        F.col("to_address"),
        F.col("value"),
        F.col("gas_price"),
        F.col("gas").alias("gas_limit"),
        F.col("tx_timestamp"),
        type_transaction.alias("type_transaction"),
        F.col("block_gas_limit"),
        F.col("block_gas_used"),
        gas_pct_of_block.alias("gas_pct_of_block"),
        F.col("base_fee_per_gas"),
    )


# COMMAND ----------
# MAGIC %md
# MAGIC ## Gold 4 — Transactions Lambda → `s_apps.transactions_lambda`
# MAGIC
# MAGIC Materialized view que combina dados de streaming (`transactions_ethereum`)
# MAGIC com dados batch (`popular_contracts_txs`) para criar uma visão unificada
# MAGIC (arquitetura Lambda) das transações dos contratos populares, sempre com
# MAGIC o input decodificado mais preciso disponível.

# COMMAND ----------

@dlt.table(
    name="s_apps.transactions_lambda",
    comment="Gold MV: visão Lambda unindo streaming (transactions_fast) e batch (popular_contracts_txs) com input decodificado",
    table_properties={
        "quality": "gold",
        "pipelines.autoOptimize.managed": "true",
    },
)
def gold_transactions_lambda():
    """
    Lambda view:
    - streaming_layer: transactions_fast (real-time, com method/parms do decoder)
    - batch_layer: popular_contracts_txs (histórico horário Etherscan, com input completo)

    UNION ALL com deduplicação: se a mesma tx_hash existe em ambas, prioriza o batch
    (pois input vindo do Etherscan é mais confiável/completo).
    """
    # ── Streaming: transactions_ethereum filtrada apenas para contratos populares──
    df_ranking = dlt.read("s_apps.popular_contracts_ranking").select("contract_address")
    df_stream = dlt.read("s_apps.transactions_ethereum")

    df_stream_popular = (
        df_stream
        .join(df_ranking, df_stream.to_address == df_ranking.contract_address, "inner")
        .select(
            F.col("tx_hash"),
            F.col("block_number"),
            F.col("from_address"),
            F.col("to_address").alias("contract_address"),
            F.col("value"),
            F.col("gas"),
            F.col("gas_price"),
            F.col("input"),
            # Input decodificado (vem de transactions_ethereum via JOIN com topic 5)
            F.col("method"),
            F.col("parms"),
            F.col("decode_type"),
            F.col("input_etherscan"),
            F.col("tx_timestamp").alias("event_time"),
            F.lit("streaming").alias("source_layer"),
        )
    )

    # ── Batch: popular_contracts_txs (já em Bronze) ──────────────────────────
    df_batch = spark.table(f"{CATALOG}.b_ethereum.popular_contracts_txs")

    df_batch_enriched = (
        df_batch
        .select(
            F.col("tx_hash"),
            F.col("block_number"),
            F.col("from_address"),
            F.col("contract_address"),
            F.col("value"),
            F.col("gas_used").alias("gas"),
            F.lit(None).cast("long").alias("gas_price"),
            F.col("input"),
            F.lit(None).cast("string").alias("method"),
            F.lit(None).cast("string").alias("parms"),
            F.lit(None).cast("string").alias("decode_type"),
            F.lit(None).cast("string").alias("input_etherscan"),
            F.col("timestamp").alias("event_time"),
            F.lit("batch").alias("source_layer"),
        )
    )

    # ── UNION com deduplicação: prioridade por completude do decode_type ──────
    # Ordem de prioridade (TODO-P05):
    #   1. decode_type='full'       → método + parâmetros via ABI Etherscan (mais completo)
    #   2. decode_type='full_4byte' → método + parâmetros via 4byte.directory
    #   3. decode_type='partial'    → apenas nome do método decodificado
    #   4. source_layer='batch'     → input raw completo do Etherscan (sem decode)
    #   5. decode_type='unknown'    → apenas seletor 4-byte hex (menos informativo)
    df_union = df_stream_popular.unionByName(df_batch_enriched)

    return (
        df_union
        .withColumn(
            "_rank",
            F.row_number().over(
                Window.partitionBy("tx_hash").orderBy(
                    F.when(F.col("decode_type") == "full",       F.lit(1))
                     .when(F.col("decode_type") == "full_4byte",  F.lit(2))
                     .when(F.col("decode_type") == "partial",     F.lit(3))
                     .when(F.col("source_layer") == "batch",      F.lit(4))
                     .when(F.col("decode_type") == "unknown",     F.lit(5))
                     .otherwise(F.lit(6))
                )
            )
        )
        .filter(F.col("_rank") == 1)
        .drop("_rank")
    )


# COMMAND ----------
# MAGIC %md
# MAGIC ## Gold 5 — Network Metrics Hourly → `g_network.network_metrics_hourly`
# MAGIC
# MAGIC Métricas agredadas da rede Ethereum por hora: TPS médio, preço de gas,
# MAGIC utilização de blocos e volume de transações (TODO-P06).

# COMMAND ----------

@dlt.table(
    name="g_network.network_metrics_hourly",
    comment="Gold MV: métricas horárias da rede Ethereum — TPS, gas médio, utilização de blocos",
    table_properties={
        "quality": "gold",
        "pipelines.autoOptimize.managed": "true",
    },
)
def gold_network_metrics_hourly():
    """
    Agrega métricas da rede Ethereum por hora usando blocks_fast e transactions_fast.

    Métricas calculadas:
    - block_count               : blocos produzidos na hora
    - tx_count                  : total de transações
    - tps_avg                   : TPS médio (tx_count / 3600 segundos)
    - avg_gas_price_gwei        : preço médio do gas em Gwei
    - avg_block_gas_used        : gas médio usado por bloco
    - avg_block_gas_limit       : gas limit médio por bloco
    - avg_block_utilization_pct : utilização média do bloco (gas_used/gas_limit × 100)
    - avg_txs_per_block         : média de transações por bloco
    """
    blocks = (
        dlt.read("s_apps.blocks_fast")
        .select(
            F.date_trunc("hour", F.col("block_time")).alias("hour_bucket"),
            F.col("block_number"),
            F.col("gas_used").alias("block_gas_used"),
            F.col("gas_limit").alias("block_gas_limit"),
            F.col("transaction_count"),
        )
    )

    txs = (
        dlt.read("s_apps.transactions_fast")
        .select(
            F.date_trunc("hour", F.col("kafka_timestamp")).alias("hour_bucket"),
            F.col("tx_hash"),
            F.col("gas_price"),
        )
    )

    blocks_agg = (
        blocks
        .groupBy("hour_bucket")
        .agg(
            F.count("block_number").alias("block_count"),
            F.sum("transaction_count").alias("tx_count_from_blocks"),
            F.avg("block_gas_used").alias("avg_block_gas_used"),
            F.avg("block_gas_limit").alias("avg_block_gas_limit"),
            F.avg(
                F.when(
                    F.col("block_gas_limit") > 0,
                    F.col("block_gas_used").cast("double") / F.col("block_gas_limit") * 100,
                ).otherwise(F.lit(None))
            ).alias("avg_block_utilization_pct"),
            F.avg("transaction_count").alias("avg_txs_per_block"),
        )
    )

    txs_agg = (
        txs
        .groupBy("hour_bucket")
        .agg(
            F.count("tx_hash").alias("tx_count"),
            F.avg(F.col("gas_price").cast("double") / 1e9).alias("avg_gas_price_gwei"),
        )
    )

    return (
        blocks_agg
        .join(txs_agg, "hour_bucket", "left")
        .select(
            F.col("hour_bucket"),
            F.col("block_count"),
            F.coalesce(F.col("tx_count"), F.col("tx_count_from_blocks")).alias("tx_count"),
            F.round(
                F.coalesce(F.col("tx_count"), F.col("tx_count_from_blocks")).cast("double") / 3600,
                2,
            ).alias("tps_avg"),
            F.round(F.col("avg_gas_price_gwei"), 4).alias("avg_gas_price_gwei"),
            F.round(F.col("avg_block_gas_used"), 0).alias("avg_block_gas_used"),
            F.round(F.col("avg_block_gas_limit"), 0).alias("avg_block_gas_limit"),
            F.round(F.col("avg_block_utilization_pct"), 2).alias("avg_block_utilization_pct"),
            F.round(F.col("avg_txs_per_block"), 1).alias("avg_txs_per_block"),
            F.current_timestamp().alias("computed_at"),
        )
    )
