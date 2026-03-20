###############################################################################
# terraform_dev/s3.tf
#
# Bucket S3 para ingestão de dados Kafka → Databricks Free Edition.
#
# O job Spark local (spark-stream-txs) escreve dados dos tópicos Kafka neste
# bucket em formato Parquet, particionado por topic_name.
#
# O Databricks Free Edition lê deste bucket via external location configurado
# manualmente na UI (Instance Profile ou Access Key).
###############################################################################

resource "aws_s3_bucket" "ingestion" {
  bucket = var.bucket_name
  tags   = { Name = var.bucket_name }
}

resource "aws_s3_bucket_versioning" "ingestion" {
  bucket = aws_s3_bucket.ingestion.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "ingestion" {
  bucket = aws_s3_bucket.ingestion.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "ingestion" {
  bucket                  = aws_s3_bucket.ingestion.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Prefixos de pasta para organização
resource "aws_s3_object" "raw_prefix" {
  bucket  = aws_s3_bucket.ingestion.id
  key     = "raw/.keep"
  content = ""
}
