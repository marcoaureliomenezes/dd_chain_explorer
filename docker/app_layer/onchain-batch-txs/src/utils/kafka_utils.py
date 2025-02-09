from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer, AvroSerializer
from confluent_kafka.serialization import StringSerializer, StringDeserializer
from confluent_kafka import DeserializingConsumer, SerializingProducer


class KafkaUtils:

  def __init__(self, logger, sc_url):
    self.logger = logger
    self.sc_client = SchemaRegistryClient({'url': sc_url})

  def create_avro_producer(self, producer_configs, avro_schema) -> SerializingProducer:
    avro_serializer = AvroSerializer(self.sc_client, avro_schema, lambda msg, ctx: dict(msg))
    producer_configs['key.serializer'] = StringSerializer('utf_8')
    producer_configs['value.serializer'] = avro_serializer
    return SerializingProducer(producer_configs)
  

  def create_avro_consumer(self, consumer_configs, avro_schema) -> DeserializingConsumer:
    avro_deserializer = AvroDeserializer(self.c_client, avro_schema, lambda msg, ctx: dict(msg))
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

