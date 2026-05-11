#!/usr/bin/env bash
set -euo pipefail

: "${RELEASE_IMG:?RELEASE_IMG is required}"
: "${ECS_CLUSTER:?ECS_CLUSTER is required}"

SERVICES="${SERVICES:-dm-mined-blocks-watcher dm-orphan-blocks-watcher dm-block-data-crawler dm-mined-txs-crawler dm-txs-input-decoder}"

for SVC in $SERVICES; do
  TASK_DEF=$(aws ecs describe-task-definition --task-definition "$SVC" --query 'taskDefinition' --output json)
  NEW_TASK_DEF=$(echo "$TASK_DEF" | jq \
    --arg img "$RELEASE_IMG" \
    '.containerDefinitions[0].image = $img | del(.taskDefinitionArn,.revision,.status,.requiresAttributes,.placementConstraints,.compatibilities,.registeredAt,.registeredBy)')
  NEW_TASK_ARN=$(aws ecs register-task-definition --cli-input-json "$NEW_TASK_DEF" --query 'taskDefinition.taskDefinitionArn' --output text)
  aws ecs update-service --cluster "$ECS_CLUSTER" --service "$SVC" \
    --task-definition "$NEW_TASK_ARN" --force-new-deployment --query 'service.serviceName'
done
