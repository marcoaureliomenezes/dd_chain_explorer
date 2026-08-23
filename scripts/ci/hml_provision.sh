#!/usr/bin/env bash
# HML minimal-lane provisioning (B2/A3).
#
# HML no longer runs an ephemeral streaming test environment: the compute
# cluster, security groups and the streaming-delivery resources it used to provision
# were all deleted with the capture lane (T-B.2, DRIFT-02/DRIFT-13). The
# minimal HML lane is exactly the two Terraform-managed buckets declared in
# services/hml/04_peripherals (dm-chain-explorer-hml-raw-data,
# dm-chain-explorer-hml-lakehouse) plus the dm-databricks-hml-s3-role Unity
# Catalog credential (T-B.4/T-C.7) — nothing ephemeral to provision per run.
#
# This script is kept as a callable no-op so callers that still invoke it
# do not need to be deleted in the same commit; it exits 0 immediately.
set -euo pipefail

echo "==> HML minimal lane: nothing to provision (capture lane retired, B2/A3)."
