#!/usr/bin/env bash
# Creates the ephemeral per-run HML resources for streaming integration tests:
#   - Security group (unique per CI run)
#
# Persistent resources (ECS cluster, ECR, Kinesis, SQS, Firehose, DynamoDB,
# CloudWatch, S3, VPC, IAM) are ALL Terraform-managed (services/hml/).
# Run 'Deploy Infra Cloud' (hml) once before using this workflow.
# Kinesis is re-created by all-hml-infra-apply at the start of each pipeline run.
#
# Workflow-level env vars used directly (auto-available on runner):
#   HML_ECS_CLUSTER — e.g. dm-chain-explorer-ecs-hml
#   AWS_REGION      — e.g. sa-east-1
#
# Required env vars (must be set in workflow step env:):
#   HML_VPC_ID — VPC ID for the HML security group (from secrets)
#
# Default GitHub Actions env vars used:
#   GITHUB_RUN_ID — used to make the SG name unique per run
#
# Writes to GITHUB_OUTPUT:
#   hml_sg_id            — ID of the created ephemeral security group
#   sqs_url_mined_blocks — SQS queue URL for mainnet-mined-blocks-events-hml
#   sqs_url_txs_hash_ids — SQS queue URL for mainnet-block-txs-hash-id-hml
set -euo pipefail

REGION="${AWS_REGION}"

# ── Retrieve SQS queue URLs (Terraform-managed, always present) ───────────────
echo "==> Retrieving HML SQS queue URLs..."
URL_MINED=$(aws sqs get-queue-url --queue-name "mainnet-mined-blocks-events-hml" \
  --region "${REGION}" --query 'QueueUrl' --output text)
URL_TXS=$(aws sqs get-queue-url --queue-name "mainnet-block-txs-hash-id-hml" \
  --region "${REGION}" --query 'QueueUrl' --output text)

echo "sqs_url_mined_blocks=${URL_MINED}" >> "${GITHUB_OUTPUT}"
echo "sqs_url_txs_hash_ids=${URL_TXS}"  >> "${GITHUB_OUTPUT}"

# ── Ephemeral security group ──────────────────────────────────────────────────
echo "==> Creating HML security group..."
HML_SG_ID=$(aws ec2 create-security-group \
  --group-name "dm-hml-sg-${GITHUB_RUN_ID}" \
  --description "HML ephemeral SG run=${GITHUB_RUN_ID}" \
  --vpc-id "${HML_VPC_ID}" \
  --query 'GroupId' --output text)

echo "hml_sg_id=${HML_SG_ID}" >> "${GITHUB_OUTPUT}"

aws ec2 authorize-security-group-ingress \
  --group-id "${HML_SG_ID}" --protocol tcp --port 0-65535 --source-group "${HML_SG_ID}"
aws ec2 authorize-security-group-egress \
  --group-id "${HML_SG_ID}" \
  --ip-permissions '[{"IpProtocol":"tcp","FromPort":443,"ToPort":443,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]' 2>/dev/null || true

echo "==> HML environment provisioned — SG: ${HML_SG_ID}"
