"""Fixture unit tests for scripts/ci/resolve_layer_or_skip.sh — the non-gating
advisory-plan wrapper around resolve_layer.sh used only by plan_on_pr.yml's
plan-prd-lambda job and drift_detection.yml's drift-prd-lambda job (addendum to
the F-01..F-12 public-repo CI security remediation, 2026-08-23).

Intent: CONTRACT — addendum (skip prd/06_lambda's advisory plan when the
lambda-layer artifact store is not yet provisioned, instead of failing the job;
never mask a real failure as a skip).

Exercised against the same stub `aws` binary as test_resolve_layer.py, placed
first on PATH — no real AWS calls, no network.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

CI_DIR = Path(__file__).resolve().parents[1]
SCRIPT = CI_DIR / "resolve_layer_or_skip.sh"

_AWS_STUB = """\
#!/usr/bin/env bash
# Test-only stand-in for the `aws` CLI (scripts/ci/tests/test_resolve_layer_or_skip.py).
set -euo pipefail

sub="$1 $2"
case "$sub" in
  "s3api list-objects-v2")
    if [ -n "${STUB_LIST_OBJECTS_ERROR:-}" ]; then
      echo "${STUB_LIST_OBJECTS_ERROR}" >&2
      exit "${STUB_LIST_OBJECTS_EXIT_CODE:-255}"
    fi
    echo "${STUB_LATEST_KEY:-None}"
    ;;
  "s3api head-object")
    echo "${STUB_METADATA_SHA256:-None}"
    ;;
  *)
    echo "unstubbed aws invocation: $*" >&2
    exit 99
    ;;
esac
"""


@pytest.fixture()
def stub_path(tmp_path: Path) -> Path:
    """A directory containing only the stub `aws`, for prepending to PATH."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    aws_stub = bin_dir / "aws"
    aws_stub.write_text(_AWS_STUB)
    aws_stub.chmod(aws_stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return bin_dir


def _run(stub_path: Path, extra_env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PATH"] = f"{stub_path}:{env.get('PATH', '')}"
    env.update(extra_env)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_usage_error_on_wrong_arg_count(stub_path: Path) -> None:
    res = _run(stub_path, {}, "only-one-arg")
    assert res.returncode == 2
    assert "Usage:" in res.stderr


def test_resolves_and_reports_skip_false(stub_path: Path) -> None:
    sha = "e" * 64
    key = f"lambda-layers/dm-chain-utils/{sha}.zip"
    res = _run(
        stub_path,
        {"STUB_LATEST_KEY": key, "STUB_METADATA_SHA256": "None"},
        "dm-chain-explorer-artifacts",
        "lambda-layers/dm-chain-utils/",
    )
    assert res.returncode == 0, res.stderr
    assert f"LAYER_S3_KEY={key}" in res.stdout
    assert "skip=false" in res.stdout
    assert "skip=true" not in res.stdout


def test_skips_gracefully_when_store_not_yet_provisioned(stub_path: Path) -> None:
    """The addendum's core behaviour: a missing bucket must warn + skip (exit 0),
    never fail the job."""
    res = _run(
        stub_path,
        {
            "STUB_LIST_OBJECTS_ERROR": (
                "An error occurred (NoSuchBucket) when calling the ListObjectsV2 "
                "operation: The specified bucket does not exist"
            ),
            "STUB_LIST_OBJECTS_EXIT_CODE": "255",
        },
        "dm-chain-explorer-artifacts",
        "lambda-layers/dm-chain-utils/",
    )
    assert res.returncode == 0, res.stderr
    assert "skip=true" in res.stdout
    assert "::warning::" in res.stdout
    assert "prd/06_lambda plan skipped" in res.stdout
    assert "v0.5.0-live-cutover.md" in res.stdout


def test_skips_gracefully_when_prefix_exists_but_is_empty(stub_path: Path) -> None:
    """An existing bucket with no matching objects yet is the same 'not yet
    provisioned' signal as a missing bucket — both must skip, not fail."""
    res = _run(
        stub_path,
        {"STUB_LATEST_KEY": "None"},
        "dm-chain-explorer-artifacts",
        "lambda-layers/dm-chain-utils/",
    )
    assert res.returncode == 0, res.stderr
    assert "skip=true" in res.stdout


def test_propagates_real_failures_never_skips(stub_path: Path) -> None:
    """A genuine AWS failure (auth, throttling, ...) must never be masked as a
    skip — it propagates as a hard failure with the real error on stderr."""
    res = _run(
        stub_path,
        {
            "STUB_LIST_OBJECTS_ERROR": (
                "An error occurred (AccessDenied) when calling the ListObjectsV2 operation"
            ),
            "STUB_LIST_OBJECTS_EXIT_CODE": "255",
        },
        "dm-chain-explorer-artifacts",
        "lambda-layers/dm-chain-utils/",
    )
    assert res.returncode != 0
    assert "skip=true" not in res.stdout
    assert "AccessDenied" in res.stderr
