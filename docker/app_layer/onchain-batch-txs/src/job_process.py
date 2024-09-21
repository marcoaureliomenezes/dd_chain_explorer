from io import BytesIO
from hdfs import InsecureClient
import duckdb
import pandas as pd

import pyarrow.parquet as pa

# Connect to HDFS
client = InsecureClient('http://namenode:9870')

# Download file from HDFS to local

base_path = '/raw/batch/contract_transactions/0x7a250d/year=2024/month=07/day=21/hour=02/'
client.download('/raw/batch/contract_transactions/0x7a250d/year=2024/month=07/day=21/hour=02/20351942_20351970.parquet', '20351942_20351970.parquet')

df = pa.read_table('20351942_20351970.parquet', use_pandas_metadata=True).to_pandas()


print(df.head())
# Process data with DuckDB
con = duckdb.connect()
con.execute("CREATE TABLE my_table AS SELECT * FROM df")
results = con.execute("SELECT * FROM my_table").fetchdf()

# Example query
print(results.head())