###############################################################################
# terraform_hml/s3.tf
#
# Bucket S3 para ingestão de dados no ambiente HML.
#
# Fluxo: Kafka (ECS Fargate efêmero) → Spark/app → S3 (este bucket)
#        → Databricks Free Edition (DABs HML, catálogo "hml")
#
# O bucket persiste entre runs de CI/CD. O conteúdo pode ser limpo
# manualmente ou via lifecycle rule.
###############################################################################

resource "aws_s3_bucket" "hml_ingestion" {
  bucket = var.ingestion_bucket_name
  tags   = { Name = var.ingestion_bucket_name }
}

resource "aws_s3_bucket_versioning" "hml_ingestion" {
  bucket = aws_s3_bucket.hml_ingestion.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "hml_ingestion" {
  bucket = aws_s3_bucket.hml_ingestion.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "hml_ingestion" {
  bucket                  = aws_s3_bucket.hml_ingestion.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "hml_ingestion" {
  bucket = aws_s3_bucket.hml_ingestion.id

  rule {
    id     = "expire-hml-data"
    status = "Enabled"
    expiration { days = 7 }
  }
}

resource "aws_s3_object" "raw_prefix" {
  bucket  = aws_s3_bucket.hml_ingestion.id
  key     = "raw/.keep"
  content = ""
}
