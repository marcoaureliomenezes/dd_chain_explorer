#!/usr/bin/env bash
# Tears down the ephemeral HML environment created by hml_provision.sh:
#   - Stops and deregisters ECS tasks/task definitions
#   - Deletes ECS cluster + security group
#   - Deletes DynamoDB table, Kinesis streams, SQS queues, Firehose streams
#
# Workflow-level env vars used directly (auto-available on runner):
#   HML_ECS_CLUSTER — e.g. dm-hml-ecs
#   AWS_REGION      — e.g. sa-east-1
#
# Required env vars (must be set in workflow step env:):
#   HML_SG_ID — security group ID from the provision step outputs
set -euo pipefail

REGION="${AWS_REGION}"

# ── Stop ECS tasks ─────────────────────────────────────────────────────────────
echo "==> Stopping HML ECS tasks..."
TASKS=$(aws ecs list-tasks --cluster "${HML_ECS_CLUSTER}" \
  --query 'taskArns' --output json 2>/dev/null || echo '[]')
for TASK_ARN in $(echo "$TASKS" | jq -r '.[]'); do
  aws ecs stop-task --cluster "${HML_ECS_CLUSTER}" --task "$TASK_ARN" \
    --reason "HML teardown" 2>/dev/null || true
done

# ── Deregister task definitions ───────────────────────────────────────────────
echo "==> Deregistering HML task definitions..."
for FAMILY in hml-dm-mined-blocks-watcher hml-dm-orphan-blocks-watcher \
              hml-dm-block-data-crawler hml-dm-mined-txs-crawler hml-dm-txs-input-decoder; do
  REVISIONS=$(aws ecs list-task-definitions --family-prefix "$FAMILY" \
    --query 'taskDefinitionArns' --output json 2>/dev/null || echo '[]')
  for ARN in $(echo "$REVISIONS" | jq -r '.[]'); do
    aws ecs deregister-task-definition --task-definition "$ARN" \
      --query 'taskDefinition.taskDefinitionArn' --output text 2>/dev/null || true
  done
done

# ── Delete ECS cluster + security group ──────────────────────────────────────
echo "==> Deleting HML ECS cluster..."
aws ecs delete-cluster --cluster "${HML_ECS_CLUSTER}" 2>/dev/null || true

if [ -n "${HML_SG_ID:-}" ]; then
  echo "==> Deleting HML security group ${HML_SG_ID} (waiting 20s for tasks to stop)..."
  sleep 20
  aws ec2 delete-security-group --group-id "${HML_SG_ID}" 2>/dev/null || true
fi

# ── Delete DynamoDB + Kinesis + SQS + Firehose ───────────────────────────────
echo "==> Deleting HML DynamoDB table..."
aws dynamodb delete-table --table-name "dm-chain-explorer-hml" \
  --region "${REGION}" 2>/dev/null || true

echo "==> Deleting HML Kinesis streams + Firehose delivery streams..."
for STREAM in mainnet-blocks-data mainnet-transactions-data mainnet-transactions-decoded; do
  aws kinesis delete-stream --stream-name "${STREAM}-hml" \
    --enforce-consumer-deletion --region "${REGION}" 2>/dev/null || true
  aws firehose delete-delivery-stream --delivery-stream-name "firehose-${STREAM}-hml" \
    --region "${REGION}" 2>/dev/null || true
done

echo "==> Deleting HML SQS queues..."
for Q in mainnet-mined-blocks-events-hml mainnet-block-txs-hash-id-hml \
          mainnet-mined-blocks-events-dlq-hml mainnet-block-txs-hash-id-dlq-hml; do
  URL=$(aws sqs get-queue-url --queue-name "$Q" --region "${REGION}" \
    --query 'QueueUrl' --output text 2>/dev/null) || continue
  [ -n "$URL" ] && aws sqs delete-queue --queue-url "$URL" --region "${REGION}" 2>/dev/null || true
done

echo "==> HML teardown complete."
