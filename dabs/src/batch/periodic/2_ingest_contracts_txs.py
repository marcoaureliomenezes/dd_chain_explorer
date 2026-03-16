# Databricks notebook source
# Periodic — Ingere transações históricas de contratos populares via Etherscan
# Equivalente ao AS-IS: spark-batch-jobs/periodic_spark_processing/2_ingest_txs_data_to_bronze.py

import boto3
import boto3.dynamodb.conditions
import requests
from datetime import datetime, date
from pyspark.sql import Row
from pyspark.sql.types import *

catalog        = dbutils.widgets.get("catalog")
raw_s3_bucket  = dbutils.widgets.get("raw_s3_bucket")
try:
    dynamodb_table = dbutils.widgets.get("dynamodb_table")
except Exception:
    dynamodb_table = "dm-popular-contracts"

# -----------------------------------------------------------------------
# Lê contratos populares do DynamoDB (single-table: PK=CONTRACT)
# -----------------------------------------------------------------------
dynamodb         = boto3.resource("dynamodb")
table            = dynamodb.Table(dynamodb_table)
response         = table.query(
    KeyConditionExpression=boto3.dynamodb.conditions.Key("pk").eq("CONTRACT"),
)
popular          = [item["sk"] for item in response.get("Items", [])]
print(f"[INFO] {len(popular)} popular contracts to process")

# -----------------------------------------------------------------------
# Busca transações via Etherscan (API key do SSM Parameter Store)
# -----------------------------------------------------------------------
ssm_client    = boto3.client("ssm")
ssm_response  = ssm_client.get_parameter(Name="/etherscan-api-keys/api-key-1", WithDecryption=True)
etherscan_key = ssm_response["Parameter"]["Value"]

rows = []
for contract in popular[:20]:  # limit to avoid rate-limit
    url = (
        f"https://api.etherscan.io/api"
        f"?module=account&action=txlist"
        f"&address={contract}"
        f"&startblock=0&endblock=99999999"
        f"&sort=desc&offset=100&page=1"
        f"&apikey={etherscan_key}"
    )
    resp = requests.get(url, timeout=30)
    if resp.status_code == 200:
        data = resp.json()
        if data.get("status") == "1":
            for tx in data.get("result", []):
                rows.append(Row(
                    contract_address  = contract,
                    tx_hash           = tx.get("hash"),
                    block_number      = int(tx.get("blockNumber", 0)),
                    timestamp         = datetime.fromtimestamp(int(tx.get("timeStamp", 0))),
                    from_address      = tx.get("from"),
                    to_address        = tx.get("to"),
                    value             = tx.get("value"),
                    gas_used          = int(tx.get("gasUsed", 0)),
                    input             = tx.get("input"),
                    ingestion_date    = date.today(),
                ))

if rows:
    df = spark.createDataFrame(rows)
    (
        df.write
        .format("delta")
        .mode("append")
        .partitionBy("ingestion_date")
        .saveAsTable(f"`{catalog}`.b_ethereum.popular_contracts_txs")
    )
    print(f"[OK] {len(rows)} transactions written to b_ethereum.popular_contracts_txs")
else:
    print("[WARN] No transactions fetched")
