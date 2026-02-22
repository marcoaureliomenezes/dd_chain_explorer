output "msk_bootstrap_brokers_iam" {
  description = "MSK bootstrap brokers (IAM auth)"
  value       = aws_msk_cluster.dm.bootstrap_brokers_sasl_iam
}

output "msk_bootstrap_brokers_tls" {
  description = "MSK bootstrap brokers (TLS)"
  value       = aws_msk_cluster.dm.bootstrap_brokers_tls
}

output "msk_cluster_arn" {
  value = aws_msk_cluster.dm.arn
}

output "glue_schema_registry_arn" {
  value = aws_glue_registry.dm.arn
}
