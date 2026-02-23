output "raw_bucket_name" {
  value = aws_s3_bucket.raw.bucket
}

output "raw_bucket_arn" {
  value = aws_s3_bucket.raw.arn
}

output "lakehouse_bucket_name" {
  value = aws_s3_bucket.lakehouse.bucket
}

output "lakehouse_bucket_arn" {
  value = aws_s3_bucket.lakehouse.arn
}

output "databricks_bucket_name" {
  value = aws_s3_bucket.databricks.bucket
}

output "databricks_bucket_arn" {
  value = aws_s3_bucket.databricks.arn
}
