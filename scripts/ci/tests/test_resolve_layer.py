"""Fixture unit tests for scripts/ci/resolve_layer.sh (T-A.7 leftover, WS-A).

Exercised against a stub `aws` binary placed first on PATH — no real AWS calls, no
network. The stub recognizes only the two subcommands resolve_layer.sh calls
(`s3api list-objects-v2`, `s3api head-object`) and answers from env vars the test
sets, so each scenario controls the "S3 state" without touching the real service.

Run via the repo's pytest runner:
    pytest scripts/ci/tests/test_resolve_layer.py -p no:cacheprovider
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "resolve_layer.sh"

_AWS_STUB = """\
#!/usr/bin/env bash
# Test-only stand-in for the `aws` CLI (scripts/ci/tests/test_resolve_layer.py).
set -euo pipefail

sub="$1 $2"
case "$sub" in
  "s3api list-objects-v2")
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


def test_resolves_newest_key_and_derives_sha256_from_basename(stub_path: Path) -> None:
    sha = "a" * 64
    key = f"lambda-layers/dm-chain-utils/{sha}.zip"
    res = _run(
        stub_path,
        {"STUB_LATEST_KEY": key, "STUB_METADATA_SHA256": "None"},
        "dm-chain-explorer-artifacts",
        "lambda-layers/dm-chain-utils/",
    )
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == f"LAYER_S3_KEY={key} LAYER_SHA256={sha}"


def test_matching_metadata_sha256_passes(stub_path: Path) -> None:
    sha = "b" * 64
    key = f"lambda-layers/dm-chain-utils/{sha}.zip"
    res = _run(
        stub_path,
        {"STUB_LATEST_KEY": key, "STUB_METADATA_SHA256": sha},
        "dm-chain-explorer-artifacts",
        "lambda-layers/dm-chain-utils/",
    )
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == f"LAYER_S3_KEY={key} LAYER_SHA256={sha}"


def test_no_object_under_prefix_fails_loudly(stub_path: Path) -> None:
    res = _run(
        stub_path,
        {"STUB_LATEST_KEY": "None"},
        "dm-chain-explorer-artifacts",
        "lambda-layers/dm-chain-utils/",
    )
    assert res.returncode != 0
    assert "No lambda-layer artifact found" in res.stderr
    assert "Deploy All DM Applications" in res.stderr
    assert "docs/runbooks/lambda-layer.md" in res.stderr


def test_metadata_mismatch_fails_loudly(stub_path: Path) -> None:
    key_sha = "c" * 64
    bad_metadata_sha = "d" * 64
    key = f"lambda-layers/dm-chain-utils/{key_sha}.zip"
    res = _run(
        stub_path,
        {"STUB_LATEST_KEY": key, "STUB_METADATA_SHA256": bad_metadata_sha},
        "dm-chain-explorer-artifacts",
        "lambda-layers/dm-chain-utils/",
    )
    assert res.returncode != 0
    assert "does not match" in res.stderr


def test_key_not_shaped_like_content_addressed_zip_fails(stub_path: Path) -> None:
    res = _run(
        stub_path,
        {"STUB_LATEST_KEY": "lambda-layers/dm-chain-utils/.zip"},
        "dm-chain-explorer-artifacts",
        "lambda-layers/dm-chain-utils/",
    )
    assert res.returncode != 0
    assert "does not match the expected" in res.stderr
