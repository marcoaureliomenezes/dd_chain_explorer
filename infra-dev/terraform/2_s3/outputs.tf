###############################################################################
# terraform_dev/2_s3/outputs.tf
###############################################################################

output "ingestion_bucket_name" {
  description = "Nome do bucket S3 de ingestão DEV"
  value       = aws_s3_bucket.ingestion.bucket
}

output "ingestion_bucket_arn" {
  description = "ARN do bucket S3 de ingestão DEV"
  value       = aws_s3_bucket.ingestion.arn
}
