"""Fixture unit tests for scripts/ci/plan_gate_check.sh (T-R6-A2(c), F-QA-2).

The destroy-acknowledgment gate and the cross-stack divergence gate are pure
functions of terraform `plan.txt` text, so they are exercised here against
fixture plans with no terraform/AWS calls.

Run via the repo's pytest runner:
    pytest scripts/ci/tests/test_plan_gate_check.py -p no:cacheprovider
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "plan_gate_check.sh"

# ── Fixture plan bodies ────────────────────────────────────────────────────────

NO_CHANGES_PLAN = "No changes. Your infrastructure matches the configuration.\n"

ADD_ONLY_PLAN = """\
Terraform will perform the following actions:

  # aws_s3_bucket.raw will be created
  + resource "aws_s3_bucket" "raw" {}

Plan: 1 to add, 0 to change, 0 to destroy.
"""

DESTROY_PLAN = """\
Terraform will perform the following actions:

  # aws_s3_bucket.old will be destroyed
  - resource "aws_s3_bucket" "old" {}

  # aws_iam_role.app will be created
  + resource "aws_iam_role" "app" {}

Plan: 1 to add, 0 to change, 1 to destroy.
"""

CHANGE_ONLY_PLAN = """\
Terraform will perform the following actions:

  # aws_iam_role.app will be updated in-place
  ~ resource "aws_iam_role" "app" {}

Plan: 0 to add, 1 to change, 0 to destroy.
"""


def _write(tmp_path: Path, name: str, body: str) -> str:
    p = tmp_path / name
    p.write_text(body)
    return str(p)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


# ── destroy-ack gate ───────────────────────────────────────────────────────────


def test_no_destroy_plan_passes_without_ack(tmp_path: Path) -> None:
    plan = _write(tmp_path, "p.txt", ADD_ONLY_PLAN)
    res = _run("destroy-ack", "false", plan)
    assert res.returncode == 0, res.stderr


def test_no_changes_plan_passes_without_ack(tmp_path: Path) -> None:
    plan = _write(tmp_path, "p.txt", NO_CHANGES_PLAN)
    res = _run("destroy-ack", "false", plan)
    assert res.returncode == 0, res.stderr


def test_change_only_plan_passes_without_ack(tmp_path: Path) -> None:
    plan = _write(tmp_path, "p.txt", CHANGE_ONLY_PLAN)
    res = _run("destroy-ack", "false", plan)
    assert res.returncode == 0, res.stderr


def test_destroy_plan_without_ack_fails_loudly(tmp_path: Path) -> None:
    plan = _write(tmp_path, "p.txt", DESTROY_PLAN)
    res = _run("destroy-ack", "false", plan)
    assert res.returncode == 2, f"expected exit 2, got {res.returncode}: {res.stderr}"
    assert "DESTROYS" in res.stderr


@pytest.mark.parametrize("ack", ["true", "TRUE", "yes", "1"])
def test_destroy_plan_with_ack_passes(tmp_path: Path, ack: str) -> None:
    plan = _write(tmp_path, "p.txt", DESTROY_PLAN)
    res = _run("destroy-ack", ack, plan)
    assert res.returncode == 0, res.stderr


def test_destroy_in_any_of_multiple_plans_fails(tmp_path: Path) -> None:
    safe = _write(tmp_path, "safe.txt", ADD_ONLY_PLAN)
    danger = _write(tmp_path, "danger.txt", DESTROY_PLAN)
    res = _run("destroy-ack", "false", safe, danger)
    assert res.returncode == 2, res.stderr
    assert "danger.txt" in res.stderr


def test_all_safe_multiple_plans_pass(tmp_path: Path) -> None:
    a = _write(tmp_path, "a.txt", ADD_ONLY_PLAN)
    b = _write(tmp_path, "b.txt", CHANGE_ONLY_PLAN)
    res = _run("destroy-ack", "false", a, b)
    assert res.returncode == 0, res.stderr


# ── counts subcommand ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "body,expected",
    [
        (NO_CHANGES_PLAN, "0 0 0"),
        (ADD_ONLY_PLAN, "1 0 0"),
        (CHANGE_ONLY_PLAN, "0 1 0"),
        (DESTROY_PLAN, "1 0 1"),
    ],
)
def test_counts_parsing(tmp_path: Path, body: str, expected: str) -> None:
    plan = _write(tmp_path, "p.txt", body)
    res = _run("counts", plan)
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == expected


# ── plan-diff (cross-stack divergence) gate ────────────────────────────────────


def test_plan_diff_identical_passes(tmp_path: Path) -> None:
    approved = _write(tmp_path, "approved.txt", ADD_ONLY_PLAN)
    replan = _write(tmp_path, "replan.txt", ADD_ONLY_PLAN)
    res = _run("plan-diff", approved, replan)
    assert res.returncode == 0, res.stderr


def test_plan_diff_divergent_counts_fail_closed(tmp_path: Path) -> None:
    approved = _write(tmp_path, "approved.txt", ADD_ONLY_PLAN)
    replan = _write(tmp_path, "replan.txt", DESTROY_PLAN)
    res = _run("plan-diff", approved, replan)
    assert res.returncode == 3, f"expected exit 3, got {res.returncode}: {res.stderr}"
    assert "DIVERGES" in res.stderr


def test_plan_diff_missing_approved_nondeferred_fails_closed(tmp_path: Path) -> None:
    """A NON-deferred stack with no approved pre-gate plan is a broken contract -> exit 3
    (F-QA-A1R-2: missing-approved for a non-deferred stack stays fail-closed)."""
    replan = _write(tmp_path, "replan.txt", ADD_ONLY_PLAN)
    res = _run("plan-diff", str(tmp_path / "absent.txt"), replan)
    assert res.returncode == 3, res.stderr
    assert "absent" in res.stderr.lower()


def test_plan_diff_missing_approved_deferred_takes_deferred_path(tmp_path: Path) -> None:
    """A DECLARED-deferred stack (--deferred) with no approved plan follows the informed
    post-gate deferred path, NOT unconditional exit 3 (F-QA-A1R-2, ADR-R6-5 'deferred,
    never skipped'). A no-op re-plan is allowed through (exit 0)."""
    replan = _write(tmp_path, "replan.txt", NO_CHANGES_PLAN)
    res = _run("plan-diff", "--deferred", str(tmp_path / "absent.txt"), replan)
    assert res.returncode == 0, f"deferred path must allow, got {res.returncode}: {res.stderr}"
    assert "deferred" in res.stdout.lower()


def test_plan_diff_missing_approved_deferred_with_changes_allowed(tmp_path: Path) -> None:
    """The deferred path also allows a re-plan WITH changes (the approver was informed in
    the pre-gate summary it would be planned post-upstream); the destroy-ack gate in
    deploy_env.sh guards destroys separately."""
    replan = _write(tmp_path, "replan.txt", ADD_ONLY_PLAN)
    res = _run("plan-diff", "--deferred", str(tmp_path / "absent.txt"), replan)
    assert res.returncode == 0, f"deferred path must allow, got {res.returncode}: {res.stderr}"


def test_plan_diff_deferred_still_diffs_when_approved_present(tmp_path: Path) -> None:
    """--deferred only changes the MISSING-approved behaviour; when an approved plan DOES
    exist the normal divergence comparison still applies and a divergent re-plan exits 3."""
    approved = _write(tmp_path, "approved.txt", ADD_ONLY_PLAN)
    replan = _write(tmp_path, "replan.txt", DESTROY_PLAN)
    res = _run("plan-diff", "--deferred", approved, replan)
    assert res.returncode == 3, res.stderr
    assert "DIVERGES" in res.stderr


def test_plan_diff_same_counts_different_addresses_fail(tmp_path: Path) -> None:
    a = """\
  # aws_s3_bucket.one will be created
Plan: 1 to add, 0 to change, 0 to destroy.
"""
    b = """\
  # aws_s3_bucket.two will be created
Plan: 1 to add, 0 to change, 0 to destroy.
"""
    approved = _write(tmp_path, "approved.txt", a)
    replan = _write(tmp_path, "replan.txt", b)
    res = _run("plan-diff", approved, replan)
    assert res.returncode == 3, res.stderr


# ── usage errors ───────────────────────────────────────────────────────────────


def test_unknown_subcommand_usage_error() -> None:
    res = _run("bogus")
    assert res.returncode == 64


def test_destroy_ack_missing_args_usage_error() -> None:
    res = _run("destroy-ack")
    assert res.returncode == 64
