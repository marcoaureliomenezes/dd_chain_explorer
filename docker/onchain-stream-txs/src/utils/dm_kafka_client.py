from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer, AvroSerializer
from confluent_kafka.serialization import StringSerializer, StringDeserializer
from confluent_kafka import DeserializingConsumer, SerializingProducer

import os

# In prod (APP_ENV=prod) the Schema Registry URL points to the Confluent SR ECS
# service discovered via AWS Cloud Map DNS. In dev it defaults to the local
# docker-compose service.  The value is injected via the SCHEMA_REGISTRY_URL
# env var in both environments.
_SR_URL = os.getenv("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")


class KafkaHandler:

  def __init__(self, logger, sc_url=None):
    self.logger = logger
    effective_url = sc_url if sc_url else _SR_URL
    self.sc_client = SchemaRegistryClient({'url': effective_url})

  def create_avro_producer(self, producer_configs, avro_schema) -> SerializingProducer:
    avro_serializer = AvroSerializer(
      self.sc_client,
      avro_schema,
      lambda msg, ctx: dict(msg),
      # auto.register.schemas=True (default): on first produce the schema fetched
      # from AWS Glue will be registered in the Confluent SR and the ID cached.
    )
    producer_configs['key.serializer'] = StringSerializer('utf_8')
    producer_configs['value.serializer'] = avro_serializer
    producer = SerializingProducer(producer_configs)
    # Pre-warm the broker metadata so the first produce() doesn't fail with
    # _UNKNOWN_TOPIC before librdkafka's background metadata fetch completes.
    producer.list_topics(timeout=15)
    return producer
  

  def create_avro_consumer(self, consumer_configs, avro_schema) -> DeserializingConsumer:
    avro_deserializer = AvroDeserializer(self.sc_client, avro_schema, lambda msg, ctx: dict(msg))
    consumer_configs['key.deserializer'] = StringDeserializer('utf_8')
    consumer_configs['value.deserializer'] = avro_deserializer
    return DeserializingConsumer(consumer_configs)

  def message_handler(self, err, msg):
    if err is not None: ErrorHandler(self.logger)(err)
    else: SuccessHandler(self.logger)(msg)




class SuccessHandler:

  def __init__(self, logger):
    self.logger = logger

  def __call__(self, record_metadata):
    key = record_metadata.key().decode('utf-8') if record_metadata.key() else None
    partition = record_metadata.partition()
    topic = record_metadata.topic()
    self.logger.info(f"Kafka_Ingestion;TOPIC:{topic};PARTITION:{partition};KEY:{key}")
    

class ErrorHandler:

  def __init__(self, logger):
    self.logger = logger

  def __call__(self, error):
    self.logger.error(f"Error: {error}")

