#!/usr/bin/env bash
# =============================================================================
# DEV Integration Test — onchain-stream-txs (Docker Compose)  [RETIRED v0.4.0]
#
# This suite validated the streaming capture pipeline locally: it asserted that
# the docker-compose producer containers wrote to Kinesis / Firehose / SQS and
# that Firehose delivered to S3. The dev capture layer (Kinesis, Firehose, SQS)
# was RETIRED in release v0.4.0 — capture now runs in the separate
# dd-chain-capture project (VPS + Docker Swarm + Kafka + Redis), with S3 as the
# integration boundary.
#
# Every phase asserted against now-destroyed resources, so the suite is reduced
# to a no-op skip. Capture-pipeline integration testing now lives in the
# dd-chain-capture repo.
#
# NOTE: the local-dev producer containers are still DEFINED in
# services/dev/00_compose/app_services.yml. That compose app is now orphaned
# (its dev kinesis/firehose/sqs targets are being destroyed) and is tracked as a
# follow-up cleanup outside this release's scope.
# =============================================================================
set -euo pipefail

echo "[SKIP] dev_integration_test.sh — capture layer retired in v0.4.0."
echo "       Kinesis / Firehose / SQS targets no longer exist in dev."
echo "       Capture integration testing now lives in the dd-chain-capture project."
exit 0
