###############################################################################
# terraform_dev/dynamodb.tf
#
# DynamoDB — tabela única "dm-chain-explorer" (single-table design).
#
# Substitui completamente o Redis local em DEV.
# Todos os entity types (semáforo, contador, block cache, contratos, ABI cache)
# compartilham esta tabela usando PK/SK overloaded.
#
# Entity types e chaves:
#   PK="SEMAPHORE"   SK="{api_key_name}"      → semáforo de API keys
#   PK="COUNTER"     SK="{api_key_name}"      → contagem de requisições por API key
#   PK="BLOCK_CACHE" SK="{block_number}"       → cache de hashes de blocos (orphan detection)
#   PK="CONTRACT"    SK="{contract_address}"   → contratos populares
#   PK="ABI"         SK="{contract_address}"   → ABI de contratos verificados
#   PK="ABI_NEG"     SK="{contract_address}"   → negative cache (contrato sem ABI verificada)
#
# TTL:
#   Atributo "ttl" (epoch seconds) — DynamoDB auto-deleta itens expirados.
#   SEMAPHORE: 60s | BLOCK_CACHE: 3600s | ABI_NEG: 86400s
###############################################################################

resource "aws_dynamodb_table" "chain_explorer" {
  name         = var.dynamodb_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = merge(local.common_tags, { Name = var.dynamodb_table_name })
}
