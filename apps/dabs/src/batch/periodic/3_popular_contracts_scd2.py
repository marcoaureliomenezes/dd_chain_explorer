# Databricks notebook source
# MAGIC %md
# MAGIC # SCD Type 2 — Popular Contracts Ranking History
# MAGIC
# MAGIC Mantém histórico de popularidade dos contratos populares usando
# MAGIC Slowly Changing Dimension Type 2 (TODO-P04).
# MAGIC
# MAGIC **Lógica:**
# MAGIC - Lê snapshot atual de `s_apps.popular_contracts_ranking` (gold MV do DLT)
# MAGIC - Aplica MERGE INTO em `g_contracts.popular_contracts_history` usando SCD2:
# MAGIC   - Se o contrato ainda está ativo: atualiza métricas (tx_count, unique_senders)
# MAGIC   - Se o contrato saiu do ranking (e está ativo): fecha registro atual (`valid_to`)
# MAGIC   - Se o contrato entrou no ranking: insere novo registro com `valid_from = now()`
# MAGIC - Permite rastrear evolução da popularidade ao longo do tempo
# MAGIC
# MAGIC **Schema da tabela histórica:**
# MAGIC ```
# MAGIC g_contracts.popular_contracts_history (
# MAGIC   contract_address  STRING,     -- endereço do contrato
# MAGIC   tx_count          BIGINT,     -- volume de txs no momento do snapshot
# MAGIC   unique_senders    BIGINT,     -- senders únicos no momento do snapshot
# MAGIC   first_seen        TIMESTAMP,  -- primeira tx vista (da MV)
# MAGIC   last_seen         TIMESTAMP,  -- última tx vista (da MV)
# MAGIC   valid_from        TIMESTAMP,  -- início deste registro SCD2
# MAGIC   valid_to          TIMESTAMP,  -- fim deste registro (NULL = ativo)
# MAGIC   is_current        BOOLEAN,    -- True = registro ativo/atual
# MAGIC   snapshot_ts       TIMESTAMP   -- timestamp do snapshot que gerou esta versão
# MAGIC )
# MAGIC ```

# COMMAND ----------

from pyspark.sql import functions as F
from delta.tables import DeltaTable

try:
    catalog = dbutils.widgets.get("catalog")
except Exception:
    catalog = "dd_chain_explorer"

HISTORY_TABLE = f"`{catalog}`.g_contracts.popular_contracts_history"
RANKING_TABLE = f"`{catalog}`.s_apps.popular_contracts_ranking"

NOW = F.current_timestamp()

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Criar schema e tabela histórica (se não existir)

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.g_contracts")

spark.sql(f"""
  CREATE TABLE IF NOT EXISTS {HISTORY_TABLE} (
    contract_address  STRING     NOT NULL,
    tx_count          BIGINT,
    unique_senders    BIGINT,
    first_seen        TIMESTAMP,
    last_seen         TIMESTAMP,
    valid_from        TIMESTAMP  NOT NULL,
    valid_to          TIMESTAMP,
    is_current        BOOLEAN    NOT NULL,
    snapshot_ts       TIMESTAMP  NOT NULL
  )
  USING DELTA
  PARTITIONED BY (is_current)
  TBLPROPERTIES (
    'quality'                              = 'gold',
    'delta.enableChangeDataFeed'           = 'true',
    'pipelines.autoOptimize.managed'       = 'true'
  )
""")

print(f"[OK] Tabela SCD2 verificada: {HISTORY_TABLE}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Lê snapshot atual do ranking

# COMMAND ----------

df_snapshot = (
    spark.table(RANKING_TABLE)
    .select(
        F.col("contract_address"),
        F.col("tx_count"),
        F.col("unique_senders"),
        F.col("first_seen"),
        F.col("last_seen"),
        NOW.alias("snapshot_ts"),
    )
)

count_snapshot = df_snapshot.count()
print(f"[INFO] Snapshot atual: {count_snapshot} contratos no ranking")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Aplica MERGE INTO com lógica SCD Type 2

# COMMAND ----------

history_table = DeltaTable.forName(spark, HISTORY_TABLE)

# Passo 1: Fechar registros ativos que saíram do ranking
# (contract não aparece no snapshot atual mas ainda está marcado como is_current=true)
history_table.alias("h").merge(
    df_snapshot.alias("s"),
    "h.contract_address = s.contract_address AND h.is_current = true",
).whenNotMatchedBySource(
    condition="h.is_current = true",
).updateAll(
    set={
        "valid_to":   "current_timestamp()",
        "is_current": "false",
    }
).execute()

# Passo 2: Inserir novos registros para contratos que (re)entraram no ranking
# (não existe registro ativo para este contrato)
new_entries = (
    df_snapshot.alias("s")
    .join(
        spark.table(HISTORY_TABLE).filter("is_current = true").select("contract_address").alias("h"),
        "contract_address",
        "left_anti",  # apenas contratos SEM registro ativo
    )
    .select(
        F.col("s.contract_address"),
        F.col("s.tx_count"),
        F.col("s.unique_senders"),
        F.col("s.first_seen"),
        F.col("s.last_seen"),
        NOW.alias("valid_from"),
        F.lit(None).cast("timestamp").alias("valid_to"),
        F.lit(True).alias("is_current"),
        F.col("s.snapshot_ts"),
    )
)

new_entries.write.format("delta").mode("append").saveAsTable(HISTORY_TABLE)

count_new = new_entries.count()
print(f"[OK] Inseridos {count_new} novos registros SCD2")

# Passo 3: Atualizar métricas dos contratos que permanecem ativos no ranking
history_table.alias("h").merge(
    df_snapshot.alias("s"),
    "h.contract_address = s.contract_address AND h.is_current = true",
).whenMatchedUpdate(
    set={
        "tx_count":       "s.tx_count",
        "unique_senders": "s.unique_senders",
        "last_seen":      "s.last_seen",
        "snapshot_ts":    "s.snapshot_ts",
    }
).execute()

print(f"[OK] SCD2 atualizado para {HISTORY_TABLE}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Resumo

# COMMAND ----------

summary = spark.table(HISTORY_TABLE).groupBy("is_current").count()
summary.show()
