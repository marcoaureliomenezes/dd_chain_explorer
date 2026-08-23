output "raw_bucket_arn" {
  value = module.s3_raw.bucket_arn
}
output "raw_bucket_name" {
  value = module.s3_raw.bucket_name
}
output "lakehouse_bucket_arn" {
  value = module.s3_lakehouse.bucket_arn
}
output "lakehouse_bucket_name" {
  value = module.s3_lakehouse.bucket_name
}
output "databricks_hml_s3_role_arn" {
  value = aws_iam_role.databricks_hml_s3_role.arn
}
