# -----------------------------------------------------------------------
# Raw Data Bucket
# Python batch and streaming apps write raw Ethereum data here
# -----------------------------------------------------------------------
resource "aws_s3_bucket" "raw" {
  bucket = var.raw_bucket_name
  tags   = { Name = var.raw_bucket_name }
}

resource "aws_s3_bucket_versioning" "raw" {
  bucket = aws_s3_bucket.raw.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket                  = aws_s3_bucket.raw.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle: move to Infrequent Access after 30 days, Glacier after 90 days
resource "aws_s3_bucket_lifecycle_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id
  rule {
    id     = "raw-data-lifecycle"
    status = "Enabled"
    filter { prefix = "" }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }
}

# -----------------------------------------------------------------------
# Lakehouse Bucket
# Databricks / Spark Iceberg tables (Bronze, Silver, Gold)
# -----------------------------------------------------------------------
resource "aws_s3_bucket" "lakehouse" {
  bucket = var.lakehouse_bucket_name
  tags   = { Name = var.lakehouse_bucket_name }
}

resource "aws_s3_bucket_versioning" "lakehouse" {
  bucket = aws_s3_bucket.lakehouse.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lakehouse" {
  bucket = aws_s3_bucket.lakehouse.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "lakehouse" {
  bucket                  = aws_s3_bucket.lakehouse.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# -----------------------------------------------------------------------
# Folder prefixes (placeholder objects to simulate directory structure)
# -----------------------------------------------------------------------
resource "aws_s3_object" "lakehouse_bronze" {
  bucket  = aws_s3_bucket.lakehouse.id
  key     = "bronze/.keep"
  content = ""
}

resource "aws_s3_object" "lakehouse_silver" {
  bucket  = aws_s3_bucket.lakehouse.id
  key     = "silver/.keep"
  content = ""
}

resource "aws_s3_object" "lakehouse_gold" {
  bucket  = aws_s3_bucket.lakehouse.id
  key     = "gold/.keep"
  content = ""
}
