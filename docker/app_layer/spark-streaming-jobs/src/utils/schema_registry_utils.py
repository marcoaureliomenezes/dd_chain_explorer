from confluent_kafka.schema_registry import SchemaRegistryClient


class SchemaRegistryUtils:

  @staticmethod
  def get_schema_registry_client(url):
    return SchemaRegistryClient({"url": url})
  
  @staticmethod
  def get_avro_schema(schema_registry_client: SchemaRegistryClient, subject: str):
    return schema_registry_client.get_latest_version(subject).schema.schema_str
  