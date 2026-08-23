#!/usr/bin/env bash
# HML minimal-lane teardown (B2/A3).
#
# There is no ephemeral HML environment left to tear down: the compute cluster,
# security groups and streaming resources were all deleted with the capture
# lane (T-B.2, DRIFT-02/DRIFT-13). The two surviving HML buckets and the
# Unity Catalog storage credential are Terraform-managed, persistent, and
# never torn down per-run.
#
# This script is kept as a callable no-op so callers that still invoke it
# do not need to be deleted in the same commit; it exits 0 immediately.
set -euo pipefail

echo "==> HML minimal lane: nothing to tear down (capture lane retired, B2/A3)."
