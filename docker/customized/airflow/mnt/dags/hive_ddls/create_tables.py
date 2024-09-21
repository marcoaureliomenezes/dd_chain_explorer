

def create_table_b_apps_app_logs(table_fullname, table_fullpath):
  return f"""
  CREATE EXTERNAL TABLE IF NOT EXISTS {table_fullname}(
    timestamp_log INT,
    logger STRING,
    level STRING,
    filename STRING,
    function_name STRING,
    message STRING,
    year INT,
    month INT,
    day INT,
    hour INT)
  PARTITIONED BY (dat_ref_carga STRING)
  STORED BY iceberg
  STORED AS PARQUET
  LOCATION '{table_fullpath}';"""


def create_table_b_blocks_mined_blocks(table_fullname, table_fullpath):

  return f"""
    CREATE EXTERNAL TABLE IF NOT EXISTS {table_fullname} (
      number BIGINT,
      timestamp_block BIGINT,
      hash STRING,
      parentHash STRING,
      difficulty BIGINT,
      totalDifficulty STRING,
      nonce STRING,
      size BIGINT,
      miner STRING,
      baseFeePerGas BIGINT,
      gasLimit BIGINT,
      gasUsed BIGINT,
      logsBloom STRING,
      extraData STRING,
      transactionsRoot STRING,
      stateRoot STRING,
      transactions ARRAY<STRING>,
      withdrawals ARRAY<STRUCT<
        index_withdraw: BIGINT,
        validatorIndex: BIGINT,
        address: STRING,
        amount: BIGINT
      >>,
      hour INT
    )
    PARTITIONED BY (dat_ref_carga STRING)
    STORED BY iceberg
    STORED AS PARQUET
    LOCATION '{table_fullpath}';
    """



def create_table_b_blocks_mined_txs(table_fullname, table_fullpath):

  return f"""
  CREATE TABLE IF NOT EXISTS {table_fullname} (
    number BIGINT,
    timestamp_txs BIGINT,
    hash STRING,
    parentHash STRING,
    difficulty BIGINT,
    totalDifficulty STRING,
    nonce STRING,
    size BIGINT,
    miner STRING,
    baseFeePerGas BIGINT,
    gasLimit BIGINT,
    gasUsed BIGINT,
    logsBloom STRING,
    extraData STRING,
    transactionsRoot STRING,
    stateRoot STRING,
    transactions ARRAY<STRING>,
    withdrawals ARRAY<STRUCT<
        index_txs: BIGINT,
        validatorIndex: BIGINT,
        address: STRING,
        amount: BIGINT
    >>,
    hour INT
)
PARTITIONED BY (dat_ref_carga STRING)
STORED BY iceberg
STORED AS PARQUET
LOCATION '{table_fullpath}';
"""