#!/usr/bin/env bash
set -euo pipefail

: "${ECS_CLUSTER:?ECS_CLUSTER is required}"
: "${AWS_REGION:?AWS_REGION is required}"

SERVICES="${SERVICES:-dm-mined-blocks-watcher dm-orphan-blocks-watcher dm-block-data-crawler dm-mined-txs-crawler dm-txs-input-decoder}"
SUMMARY_MESSAGE="${SUMMARY_MESSAGE:-## ECS services stabilized}"

aws ecs wait services-stable \
  --cluster "$ECS_CLUSTER" \
  --services $SERVICES \
  --region "$AWS_REGION"

if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  echo "$SUMMARY_MESSAGE" >> "$GITHUB_STEP_SUMMARY"
fi
