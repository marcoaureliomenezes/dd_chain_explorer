#!/usr/bin/env bash
# Creates the ephemeral HML environment for streaming integration tests:
#   - ECS cluster
#   - Kinesis streams (ON_DEMAND)
#   - SQS queues + DLQs
#   - Firehose delivery streams
#   - Security group
#
# Workflow-level env vars used directly (auto-available on runner):
#   HML_ECS_CLUSTER — e.g. dm-hml-ecs
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

# ── ECS cluster ───────────────────────────────────────────────────────────────
echo "==> Creating HML ECS cluster..."
aws ecs create-cluster \
  --cluster-name "${HML_ECS_CLUSTER}" \
  --capacity-providers FARGATE \
  --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1 \
  --tags key=Environment,value=hml key=ManagedBy,value=cicd \
  --region "${REGION}" 2>/dev/null || echo "Cluster already exists"

aws logs describe-log-groups \
  --log-group-name-prefix "/apps/dm-chain-explorer-hml" \
  --query 'logGroups[0].logGroupName' --output text --region "${REGION}" \
  | grep -q "/apps/dm-chain-explorer-hml" \
  || { echo "::error::CW Log Group /apps/dm-chain-explorer-hml not found. Run Deploy Infra Cloud (HML) first."; exit 1; }

# ── Kinesis streams ───────────────────────────────────────────────────────────
echo "==> Creating HML Kinesis streams..."
for STREAM in mainnet-blocks-data mainnet-transactions-data mainnet-transactions-decoded; do
  aws kinesis create-stream \
    --stream-name "${STREAM}-hml" \
    --stream-mode-details StreamMode=ON_DEMAND \
    --region "${REGION}" 2>/dev/null || echo "Stream ${STREAM}-hml already exists"
done
for STREAM in mainnet-blocks-data mainnet-transactions-data mainnet-transactions-decoded; do
  aws kinesis wait stream-exists \
    --stream-name "${STREAM}-hml" \
    --region "${REGION}" 2>/dev/null || true
done

# ── SQS queues + DLQs ────────────────────────────────────────────────────────
echo "==> Creating HML SQS queues + DLQs..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

for Q in mainnet-mined-blocks-events mainnet-block-txs-hash-id; do
  aws sqs create-queue --queue-name "${Q}-dlq-hml" \
    --attributes '{"MessageRetentionPeriod":"1209600"}' \
    --region "${REGION}" 2>/dev/null || true
done

DLQ_MINED_ARN="arn:aws:sqs:${REGION}:${ACCOUNT_ID}:mainnet-mined-blocks-events-dlq-hml"
DLQ_TXS_ARN="arn:aws:sqs:${REGION}:${ACCOUNT_ID}:mainnet-block-txs-hash-id-dlq-hml"

aws sqs create-queue --queue-name "mainnet-mined-blocks-events-hml" \
  --attributes "{\"VisibilityTimeout\":\"30\",\"ReceiveMessageWaitTimeSeconds\":\"20\",\"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"${DLQ_MINED_ARN}\\\",\\\"maxReceiveCount\\\":\\\"3\\\"}\"}" \
  --region "${REGION}" 2>/dev/null || true

aws sqs create-queue --queue-name "mainnet-block-txs-hash-id-hml" \
  --attributes "{\"VisibilityTimeout\":\"60\",\"ReceiveMessageWaitTimeSeconds\":\"20\",\"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"${DLQ_TXS_ARN}\\\",\\\"maxReceiveCount\\\":\\\"3\\\"}\"}" \
  --region "${REGION}" 2>/dev/null || true

URL_MINED=$(aws sqs get-queue-url --queue-name "mainnet-mined-blocks-events-hml" \
  --region "${REGION}" --query 'QueueUrl' --output text)
URL_TXS=$(aws sqs get-queue-url --queue-name "mainnet-block-txs-hash-id-hml" \
  --region "${REGION}" --query 'QueueUrl' --output text)

echo "sqs_url_mined_blocks=${URL_MINED}" >> "${GITHUB_OUTPUT}"
echo "sqs_url_txs_hash_ids=${URL_TXS}"  >> "${GITHUB_OUTPUT}"

# ── Firehose delivery streams ─────────────────────────────────────────────────
echo "==> Creating HML Firehose delivery streams..."
FIREHOSE_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/dm-hml-firehose-role"
BUCKET_ARN="arn:aws:s3:::dm-chain-explorer-hml-raw"

for STREAM in mainnet-blocks-data mainnet-transactions-data mainnet-transactions-decoded; do
  KINESIS_ARN="arn:aws:kinesis:${REGION}:${ACCOUNT_ID}:stream/${STREAM}-hml"
  FIREHOSE_NAME="firehose-${STREAM}-hml"
  aws firehose create-delivery-stream --region "${REGION}" \
    --cli-input-json "$(jq -n \
      --arg name   "${FIREHOSE_NAME}" \
      --arg karn   "${KINESIS_ARN}" \
      --arg frole  "${FIREHOSE_ROLE_ARN}" \
      --arg barn   "${BUCKET_ARN}" \
      --arg stream "${STREAM}" \
      '{DeliveryStreamName:$name,DeliveryStreamType:"KinesisStreamAsSource",KinesisStreamSourceConfiguration:{KinesisStreamARN:$karn,RoleARN:$frole},ExtendedS3DestinationConfiguration:{RoleARN:$frole,BucketARN:$barn,Prefix:("raw/"+$stream+"/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/hour=!{timestamp:HH}/"),ErrorOutputPrefix:("raw/"+$stream+"_errors/!{firehose:error-output-type}/year=!{timestamp:yyyy}/"),BufferingHints:{SizeInMBs:1,IntervalInSeconds:60},CompressionFormat:"GZIP"}}')" \
    2>/dev/null || echo "Firehose ${FIREHOSE_NAME} already exists"
done

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
