# -----------------------------------------------------------------------
# API Key Consumption Table
# Replaces Redis DB2 — tracks daily API call counts per key
# Schema: pk = api_key_name (S), sk = date (S)
# -----------------------------------------------------------------------
resource "aws_dynamodb_table" "api_key_consumption" {
  name         = "dm-api-key-consumption"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "api_key_name"
  range_key    = "date"

  attribute {
    name = "api_key_name"
    type = "S"
  }

  attribute {
    name = "date"
    type = "S"
  }

  ttl {
    attribute_name = "expire_at"
    enabled        = true
  }

  tags = { Name = "dm-api-key-consumption" }
}

# -----------------------------------------------------------------------
# API Key Semaphore Table
# Replaces Redis DB1 — tracks which process holds which API key
# Schema: pk = api_key_name (S)
# -----------------------------------------------------------------------
resource "aws_dynamodb_table" "api_key_semaphore" {
  name         = "dm-api-key-semaphore"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "api_key_name"

  attribute {
    name = "api_key_name"
    type = "S"
  }

  ttl {
    attribute_name = "expire_at"
    enabled        = true
  }

  tags = { Name = "dm-api-key-semaphore" }
}

# -----------------------------------------------------------------------
# Popular Contracts Cache Table
# Replaces Redis DB3 — stores most-accessed Ethereum contracts
# Schema: pk = contract_address (S)
# -----------------------------------------------------------------------
resource "aws_dynamodb_table" "popular_contracts" {
  name         = "dm-popular-contracts"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "contract_address"

  attribute {
    name = "contract_address"
    type = "S"
  }

  ttl {
    attribute_name = "expire_at"
    enabled        = true
  }

  tags = { Name = "dm-popular-contracts" }
}
