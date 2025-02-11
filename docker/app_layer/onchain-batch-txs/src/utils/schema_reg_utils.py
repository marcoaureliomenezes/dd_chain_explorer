from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer, AvroSerializer
from confluent_kafka.serialization import StringSerializer, StringDeserializer
from confluent_kafka import DeserializingConsumer, SerializingProducer
import json

class SchemaRegistryUtils:

  def __init__(self, sc_url):
    self.sc_client = SchemaRegistryClient({'url': sc_url})


  def get_subjects(self):
    return self.sc_client.get_subjects()
  
  def get_schema_by_id(self, schema_id):
    return self.sc_client.get_schema(schema_id)
  
  def get_schema_by_subject(self, subject):
    schema = self.sc_client.get_latest_version(subject).schema.schema_str
    return schema
  
  def get_fixed_avro_schema(self, avro_path):
    with open(avro_path) as f:
      return json.dumps(json.load(f))

