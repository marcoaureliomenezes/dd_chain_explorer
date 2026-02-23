resource "aws_cloudwatch_log_group" "msk_broker_logs" {
  name              = "/aws/msk/dm-chain-explorer/broker-logs"
  retention_in_days = 7
  tags              = local.common_tags
}

resource "aws_kms_key" "msk_kms" {
  description             = "KMS key for MSK dm-chain-explorer encryption at rest"
  deletion_window_in_days = 7
  tags                    = local.common_tags
}

# MSK Configuration: enable auto-create topics and set default partitions
resource "aws_msk_configuration" "dm" {
  kafka_versions = [var.kafka_version]
  name           = "dm-chain-explorer-msk-config"

  server_properties = <<-EOT
    auto.create.topics.enable=false
    default.replication.factor=2
    min.insync.replicas=1
    num.partitions=8
    log.retention.hours=168
    num.io.threads=8
    num.network.threads=5
  EOT
}

resource "aws_msk_cluster" "dm" {
  cluster_name           = "dm-chain-explorer-msk"
  kafka_version          = var.kafka_version
  number_of_broker_nodes = 2 # 1 per AZ, minimal cost

  configuration_info {
    arn      = aws_msk_configuration.dm.arn
    revision = aws_msk_configuration.dm.latest_revision
  }

  broker_node_group_info {
    instance_type = var.broker_instance_type
    client_subnets = [
      data.terraform_remote_state.vpc.outputs.private_subnet_ids[0],
      data.terraform_remote_state.vpc.outputs.private_subnet_ids[1],
    ]
    storage_info {
      ebs_storage_info {
        volume_size = var.broker_ebs_size_gb
      }
    }
    security_groups = [data.terraform_remote_state.vpc.outputs.sg_msk_id]
  }

  encryption_info {
    encryption_at_rest_kms_key_arn = aws_kms_key.msk_kms.arn
    encryption_in_transit {
      client_broker = "PLAINTEXT"   # POC: plaintext dentro da VPC, sem TLS no cliente
      in_cluster    = true
    }
  }

  # Sem autenticação — segurança via Security Group (somente ECS SG acessa MSK)
  client_authentication {
    unauthenticated = true
  }

  logging_info {
    broker_logs {
      cloudwatch_logs {
        enabled   = true
        log_group = aws_cloudwatch_log_group.msk_broker_logs.name
      }
    }
  }

  tags = merge(local.common_tags, {
    Name = "dm-chain-explorer-msk"
  })
}
