import json
from typing import List
from confluent_kafka.schema_registry import SchemaRegistryClient



class SchemaRegistryHandler:

  def __init__(self, sc_url: str):
    self.sc_client = SchemaRegistryClient({'url': sc_url})


  def get_subjects(self) -> List[str]:
    return self.sc_client.get_subjects()
  
  def get_schema_by_id(self, schema_id):
    return self.sc_client.get_schema(schema_id)
  
  def get_schema_by_subject(self, subject: str):
    schema = self.sc_client.get_latest_version(subject).schema.schema_str
    return schema
  
  def delete_subject(self, subject: str):
    self.sc_client.delete_subject(subject)
  
  def get_fixed_avro_schema(self, avro_path: str) -> str:
    with open(avro_path) as f:
      return json.dumps(json.load(f))

