#!/usr/bin/env bash
# scripts/ci/resolve_layer.sh — resolve the newest built dm-chain-utils Lambda layer
# artifact in S3, for infra-only Terraform plans/applies (deploy_cloud_infra.yml,
# plan_on_pr.yml, drift_detection.yml) that have no build step of their own and
# therefore no real layer_s3_key/layer_sha256 to pass prd/06_lambda (T-A.7 leftover,
# WS-A). deploy_all_dm_applications.yml's build-layer job is the only writer of these
# objects and is the only trustworthy source of a *real* value — this script only
# reads what that job already published.
#
# Usage:
#   scripts/ci/resolve_layer.sh <bucket> <prefix>
#
# Example:
#   scripts/ci/resolve_layer.sh dm-chain-explorer-artifacts lambda-layers/dm-chain-utils/
#
# Output (last line, machine-readable, mirrors scripts/build_lambda_layer.sh's
# LAYER_ZIP=<path> LAYER_SHA256=<hex> convention):
#   LAYER_S3_KEY=<key> LAYER_SHA256=<hex>
#
# Resolution: the object is content-addressed by construction — its key is
# <prefix><sha256>.zip (deploy_all_dm_applications.yml's build-layer job). The
# basename minus the .zip suffix IS the sha256; no separate computation is needed.
# When the object carries `sha256` object metadata (set by the same upload step),
# this script cross-checks it against the key-derived hash and fails loudly on any
# mismatch — a hand-uploaded or corrupted object must never silently poison every
# downstream plan/apply. Metadata absence is not itself an error (older uploads
# predate the metadata tag).
#
# Fails loudly (clear message on stderr + non-zero exit) when the prefix holds no
# objects at all: this means deploy_all_dm_applications.yml's build-layer job has
# never run for this environment. The first deploy of a fresh environment MUST run
# that workflow (target=prod) before any infra-only plan/apply here can resolve a
# real artifact. See docs/runbooks/lambda-layer.md.

set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <bucket> <prefix>" >&2
  exit 2
fi

BUCKET="$1"
PREFIX="$2"

# Newest object under the prefix by LastModified. `list-objects-v2` does not
# guarantee any particular ordering across pages/requests, so sort client-side via
# the JMESPath query instead of trusting API response order.
LATEST_KEY="$(
  aws s3api list-objects-v2 \
    --bucket "${BUCKET}" \
    --prefix "${PREFIX}" \
    --query 'reverse(sort_by(Contents, &LastModified))[0].Key' \
    --output text
)"

if [ -z "${LATEST_KEY}" ] || [ "${LATEST_KEY}" = "None" ]; then
  echo "::error::No lambda-layer artifact found under s3://${BUCKET}/${PREFIX} — the" \
    "'Deploy All DM Applications' workflow (target=prod) builds and uploads this" \
    "object and has never run for this environment (or the bucket/prefix is wrong)." \
    "Run it once before any infra-only plan/apply can resolve a real" \
    "layer_s3_key/layer_sha256. See docs/runbooks/lambda-layer.md." >&2
  exit 1
fi

BASENAME="$(basename "${LATEST_KEY}")"
SHA256_FROM_KEY="${BASENAME%.zip}"

if [ "${BASENAME}" = "${SHA256_FROM_KEY}" ] || [ -z "${SHA256_FROM_KEY}" ]; then
  echo "::error::s3://${BUCKET}/${LATEST_KEY} does not match the expected" \
    "<sha256>.zip content-addressed key shape — refusing to guess a hash." >&2
  exit 1
fi

# Best-effort cross-check against the upload step's object metadata. A read
# failure or absent tag never blocks resolution — only a real *mismatch* does.
SHA256_FROM_METADATA="$(
  aws s3api head-object --bucket "${BUCKET}" --key "${LATEST_KEY}" \
    --query 'Metadata.sha256' --output text 2>/dev/null || true
)"

if [ -n "${SHA256_FROM_METADATA}" ] && [ "${SHA256_FROM_METADATA}" != "None" ] \
  && [ "${SHA256_FROM_METADATA}" != "${SHA256_FROM_KEY}" ]; then
  echo "::error::s3://${BUCKET}/${LATEST_KEY} metadata sha256=${SHA256_FROM_METADATA}" \
    "does not match the key-derived hash ${SHA256_FROM_KEY} — refusing to resolve a" \
    "layer artifact whose metadata disagrees with its own filename." >&2
  exit 1
fi

# aws_lambda_layer_version.source_code_hash needs base64 of the RAW sha256
# digest bytes, not the hex string embedded in the S3 key (T-R.2 F-02).
SHA256_B64="$(echo -n "${SHA256_FROM_KEY}" | xxd -r -p | base64)"

echo "LAYER_S3_KEY=${LATEST_KEY} LAYER_SHA256=${SHA256_FROM_KEY} LAYER_SHA256_B64=${SHA256_B64}"
