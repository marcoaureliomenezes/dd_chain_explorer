#!/usr/bin/env bash
# =============================================================================
# HML Integration Test (optimized) — onchain-stream-txs  [RETIRED v0.4.0]
#
# Optimized variant of hml_integration_test.sh. It validated the streaming
# capture pipeline (5 ECS producers → Kinesis / Firehose / SQS → S3). The whole
# capture layer was RETIRED in release v0.4.0 — capture now runs in the separate
# dd-chain-capture project (VPS + Docker Swarm + Kafka + Redis), with S3 as the
# integration boundary.
#
# Every phase asserted against now-destroyed resources, so the suite is reduced
# to a no-op skip. Capture-pipeline integration testing now lives in the
# dd-chain-capture repo.
# =============================================================================
set -euo pipefail

echo "[SKIP] hml_integration_test_optimized.sh — capture layer retired in v0.4.0."
echo "       Kinesis / Firehose / SQS + the 5 ECS producers no longer exist."
echo "       Capture integration testing now lives in the dd-chain-capture project."
exit 0
