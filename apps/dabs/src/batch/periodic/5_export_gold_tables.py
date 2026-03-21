# Databricks notebook source
# Periodic — Exporta tabelas Gold principais para S3 como Parquet
# Permite consumo externo dos dados Gold sem acesso direto ao Databricks.

from pyspark.sql import functions as F
from datetime import date

try:
    catalog        = dbutils.widgets.get("catalog")
    export_s3_path = dbutils.widgets.get("export_s3_path")
    export_date    = dbutils.widgets.get("export_date")
except Exception:
    catalog        = "dev"
    export_s3_path = "s3://dm-chain-explorer-lakehouse/exports"
    export_date    = date.today().strftime("%Y-%m-%d")

# (table_ref, table_name, date_filter_col_or_None)
# transactions_lambda é filtrada por event_date para evitar export total
tables = [
    (f"`{catalog}`.g_network.network_metrics_hourly", "network_metrics_hourly", None),
    (f"`{catalog}`.s_apps.popular_contracts_ranking", "popular_contracts_ranking", None),
    (f"`{catalog}`.s_apps.ethereum_gas_consume",      "ethereum_gas_consume",      None),
    (f"`{catalog}`.s_apps.transactions_lambda",       "transactions_lambda",       "event_date"),
]

results = []
for table_ref, table_name, date_col in tables:
    output_path = f"{export_s3_path}/gold/{table_name}/export_date={export_date}/"
    try:
        df = spark.table(table_ref)
        if date_col:
            df = df.filter(F.col(date_col) == F.lit(export_date))
        row_count = df.count()
        df.coalesce(1).write.mode("overwrite").parquet(output_path)
        results.append(f"[OK]   {table_name}: {row_count} rows → {output_path}")
    except Exception as e:
        results.append(f"[WARN] {table_name}: skipped — {e}")

for line in results:
    print(line)
print(f"\n[DONE] Gold export complete for export_date={export_date}")
