from pyspark.sql.types import StructType, StructField, BinaryType, IntegerType, LongType, TimestampType, StringType


class DMSchemas:


  # def create_table(self):
  #   self.create_namespace()
  #   self.spark.sql(f"""
  #   CREATE TABLE IF NOT EXISTS {self.table_name} (
  #     key BINARY                    COMMENT 'Key',
  #     value BINARY                  COMMENT 'Kafka Value Binary',   
  #     partition INT                 COMMENT 'Kafka Message Partition',
  #     offset LONG                   COMMENT 'Kafka Message Offset',
  #     ingestion_time TIMESTAMP      COMMENT 'Kafka Message Timestamp',
  #     topic STRING                  COMMENT 'Partition Field Kafka Topic',
  #     dat_ref STRING                COMMENT 'Partition Field with Date')
  #   USING ICEBERG 
  #   PARTITIONED BY (dat_ref, topic)
  #   TBLPROPERTIES ({self.get_iceberg_table_properties()})""").show()
  #   print(f"Table {self.table_name} created successfully!")
  #   self.table_exists = True
  #   return self

  @staticmethod
  def schema_bronze_multiplexed() -> StructType:
    return StructType([
      StructField("key", BinaryType(), True),
      StructField("value", BinaryType(), True),
      StructField("partition", IntegerType(), True),
      StructField("offset", LongType(), True),
      StructField("ingestion_time", TimestampType(), True),
      StructField("topic", StringType(), True),
      StructField("dat_ref", StringType(), True)
    ])


  @staticmethod
  def schema_s_blocks() -> StructType:
    return StructType([
      StructField("ingestion_time", TimestampType(), True),
      StructField("block_timestamp", TimestampType(), True),
      StructField("number", LongType(), True),
      StructField("hash", StringType(), True),
      StructField("parent_hash", StringType(), True),
      StructField("difficulty", LongType(), True),
      StructField("total_difficulty", StringType(), True),
      StructField("nonce", StringType(), True),
      StructField("size", LongType(), True),
      StructField("miner", StringType(), True),
      StructField("base_fee_per_gas", LongType(), True),
      StructField("gas_limit", LongType(), True),
      StructField("gas_used", LongType(), True),
      StructField("logs_bloom", StringType(), True),
      StructField("extra_data", StringType(), True),
      StructField("transactions_root", StringType(), True),
      StructField("state_root", StringType(), True),
      StructField("num_transactions", IntegerType(), True),
      StructField("dat_ref", StringType(), True)
    ])
  

  @staticmethod
  def schema_s_blocks_txs() -> StructType:
    return StructType([
      StructField("block_timestamp", TimestampType(), True),
      StructField("ingestion_time", TimestampType(), True),
      StructField("block_number", LongType(), True),
      StructField("transaction_id", StringType(), True),
      StructField("dat_ref", StringType(), True)
    ])
