output "msk_bootstrap_brokers" {
  description = "MSK bootstrap brokers (plaintext)"
  value       = aws_msk_cluster.dm.bootstrap_brokers
}

output "msk_bootstrap_brokers_tls" {
  description = "MSK bootstrap brokers (TLS)"
  value       = aws_msk_cluster.dm.bootstrap_brokers_tls
}

output "msk_cluster_arn" {
  value = aws_msk_cluster.dm.arn
}
