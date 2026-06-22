#!/usr/bin/env bash
# =============================================================================
# HML Integration Test — onchain-stream-txs  [RETIRED v0.4.0]
#
# This suite validated the streaming capture pipeline end-to-end: it asserted
# that the 5 ECS producer services wrote to Kinesis / Firehose / SQS and that
# Firehose delivered to S3. The entire capture layer (Kinesis, Firehose, SQS,
# and the 5 ECS producer task-defs/services) was RETIRED in release v0.4.0 —
# capture now runs in the separate dd-chain-capture project (VPS + Docker Swarm
# + Kafka + Redis). S3 remains the integration boundary between the two repos.
#
# Every phase of this suite asserted against now-destroyed resources, so the
# suite is reduced to a no-op skip. Capture-pipeline integration testing now
# lives in the dd-chain-capture repo. If you need to validate the surviving
# DynamoDB / S3 / CloudWatch survivors, do so via the relevant stack tests.
# =============================================================================
set -euo pipefail

echo "[SKIP] hml_integration_test.sh — capture layer retired in v0.4.0."
echo "       Kinesis / Firehose / SQS + the 5 ECS producers no longer exist."
echo "       Capture integration testing now lives in the dd-chain-capture project."
exit 0
