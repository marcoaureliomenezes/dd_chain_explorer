# Databricks notebook source
# DDL — Remove tabelas Silver/Gold do catálogo (teardown parcial)
# Equivalente ao AS-IS: spark-batch-jobs/ddl_iceberg_tables/job_5_delete_all_tables.py
# e ao Airflow DAG: dag_eventual_2_delete_environment.py
#
# ATENÇÃO: use somente em DEV. Irreversível em PROD.
#
# ESCOPO: apenas tabelas Silver (s_apps.*, s_logs.*) e Gold (g_api_keys.*).
# Bronze (b_ethereum.*) NÃO é apagado — preserva kafka_topics_multiplexed
# e popular_contracts_txs para reutilização no pipeline Lambda.

catalog = "dd_chain_explorer_dev"
purge   = "true"

try:
    catalog = dbutils.widgets.get("catalog")
except Exception:
    pass

try:
    purge = dbutils.widgets.get("purge")
except Exception:
    pass

purge_clause = "PURGE" if purge.lower() == "true" else ""

# ── Silver: s_logs ────────────────────────────────────────────────────────────
# Produzidas pelo pipeline dm-app-logs.
tables_s_logs = [
    f"`{catalog}`.s_logs.logs_streaming",
    f"`{catalog}`.s_logs.logs_batch",
]

# ── Silver/Gold: s_apps ───────────────────────────────────────────────────────
# Inclui todas as DLT tables (Silver 1-7 + Gold 1-4) do pipeline dm-ethereum.
# Bronze (b_ethereum.*) não é listado aqui — não será apagado.
tables_s_apps = [
    # Silver 1-4: eventos base
    f"`{catalog}`.s_apps.mined_blocks_events",
    f"`{catalog}`.s_apps.transaction_hash_ids",
    f"`{catalog}`.s_apps.blocks_fast",
    f"`{catalog}`.s_apps.transactions_fast",
    # Silver 5-7: pipeline enriquecido
    f"`{catalog}`.s_apps.txs_inputs_decoded_fast",
    f"`{catalog}`.s_apps.transactions_ethereum",
    f"`{catalog}`.s_apps.blocks_withdrawals",
    # Gold 1-4: MVs e Lambda
    f"`{catalog}`.s_apps.popular_contracts_ranking",
    f"`{catalog}`.s_apps.peer_to_peer_txs",
    f"`{catalog}`.s_apps.ethereum_gas_consume",
    f"`{catalog}`.s_apps.transactions_lambda",
]

# ── Gold: g_api_keys ──────────────────────────────────────────────────────────
# MVs de consumo de API keys, produzidas pelo pipeline dm-app-logs.
tables_g_api_keys = [
    f"`{catalog}`.g_api_keys.etherscan_consumption",
    f"`{catalog}`.g_api_keys.web3_keys_consumption",
]

tables = tables_s_logs + tables_s_apps + tables_g_api_keys

# ── Schemas Silver/Gold apenas ────────────────────────────────────────────────
# Não incluir b_ethereum — Bronze é preservado.
schemas = [
    f"`{catalog}`.s_apps",
    f"`{catalog}`.s_logs",
    f"`{catalog}`.g_api_keys",
]

print(f"[WARN] Dropping Silver/Gold tables in catalog '{catalog}' with purge={purge}")
print(f"[INFO] Bronze (b_ethereum.*) is PRESERVED — not dropped.")

for table in tables:
    try:
        spark.sql(f"DROP TABLE IF EXISTS {table} {purge_clause}")
        print(f"[OK] Table dropped: {table}")
    except Exception as e:
        print(f"[WARN] Could not drop table {table}: {e}")

for schema in schemas:
    try:
        spark.sql(f"DROP SCHEMA IF EXISTS {schema}")
        print(f"[OK] Schema dropped: {schema}")
    except Exception as e:
        print(f"[WARN] Could not drop schema {schema}: {e}")

print(f"[DONE] Silver/Gold teardown complete for catalog '{catalog}'")
