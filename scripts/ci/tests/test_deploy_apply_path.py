"""Hermetic apply-path tests for scripts/ci/deploy_env.sh (T-R6-A2(b), ADR-R6-5).

Proves the post-gate apply phase CONSUMES the downloaded approved plan artifacts
instead of blindly re-planning + applying (F-QA-A1-1):

  * upstream-unchanged stack  -> applies its SAVED approved tfplan binary;
  * stack downstream of an in-run apply (or with no saved plan) -> RE-PLANS and gates
    the fresh plan against the approved summary via plan_gate_check.sh plan-diff;
    matching re-plan applies, DIVERGING re-plan FAILS CLOSED (exit 3) with a published
    divergence diff.

terraform and aws are mocked by stub binaries on PATH (no real cloud, no real venv).
Tests run hml with SKIP_DATABRICKS=true so the stack set is vpc, peripherals, iam, ecs
(ecs.upstreams=[vpc]). Hermetic; run with `-p no:cacheprovider`.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

CI_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = CI_DIR.parents[1]
DEPLOY_ENV = CI_DIR / "deploy_env.sh"

# A terraform stub. Behaviour is driven by env vars so each test shapes plan results:
#   TF_PLAN_CHANGED_STACKS  — space-separated module basenames whose `plan` returns
#                             exit 2 (has changes) and emits a 1-add plan.txt; others
#                             return exit 0 (no changes).
#   TF_APPLY_LOG            — file each `apply` appends "<module-basename> <planarg>".
# `plan` honours -out=<file> and the redirect tf_plan.sh applies (it pipes stdout to
# plan.txt itself), so the stub writes the "Plan:" footer to STDOUT.
TF_STUB = r"""#!/usr/bin/env bash
set -u
cmd="${1:-}"
# module basename = current dir name (deploy_env cds into the module dir)
mod="$(basename "$PWD")"
case "$cmd" in
  init|validate) exit 0 ;;
  output) exit 0 ;;
  plan)
    out_file="tfplan"
    for a in "$@"; do case "$a" in -out=*) out_file="${a#-out=}";; esac; done
    : > "$out_file"  # the "saved plan binary" (stub content irrelevant)
    changed=0
    for s in ${TF_PLAN_CHANGED_STACKS:-}; do [ "$s" = "$mod" ] && changed=1; done
    if [ "$changed" = "1" ]; then
      echo "  # aws_s3_bucket.x will be created"
      echo "Plan: 1 to add, 0 to change, 0 to destroy."
      exit 2
    else
      echo "No changes. Your infrastructure matches the configuration."
      exit 0
    fi ;;
  apply)
    planarg="${!#}"
    echo "$mod $planarg" >> "${TF_APPLY_LOG:-/dev/null}"
    exit 0 ;;
  *) exit 0 ;;
esac
"""

AWS_STUB = "#!/usr/bin/env bash\necho '[]'\nexit 0\n"


def _make_bindir(tmp_path: Path) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    tf = bindir / "terraform"
    tf.write_text(TF_STUB)
    tf.chmod(0o755)
    aws = bindir / "aws"
    aws.write_text(AWS_STUB)
    aws.chmod(0o755)
    return bindir


def _stage_approved_plan(
    artifact_dir: Path, sid: str, *, has_changes: bool
) -> None:
    """Write a saved pre-gate plan (tfplan binary + plan.txt summary) for a stack."""
    sdir = artifact_dir / sid
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "tfplan").write_text("approved-saved-plan")
    if has_changes:
        (sdir / "plan.txt").write_text(
            "  # aws_s3_bucket.x will be created\n"
            "Plan: 1 to add, 0 to change, 0 to destroy.\n"
        )
    else:
        (sdir / "plan.txt").write_text(
            "No changes. Your infrastructure matches the configuration.\n"
        )


def _run(tmp_path: Path, env_extra: dict[str, str]) -> subprocess.CompletedProcess:
    bindir = _make_bindir(tmp_path)
    artifact_dir = tmp_path / ".plan-artifacts"
    div_dir = tmp_path / ".plan-divergence"
    apply_log = tmp_path / "apply.log"
    apply_log.touch()
    env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "SKIP_DATABRICKS": "true",
        "PLAN_ARTIFACT_DIR": str(artifact_dir),
        "DIVERGENCE_DIR": str(div_dir),
        "TF_APPLY_LOG": str(apply_log),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
        "GITHUB_OUTPUT": str(tmp_path / "gh_output"),
    }
    env.update(env_extra)
    proc = subprocess.run(
        ["bash", str(DEPLOY_ENV), "hml"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    proc.apply_log = apply_log.read_text() if apply_log.exists() else ""  # type: ignore[attr-defined]
    proc.div_dir = div_dir  # type: ignore[attr-defined]
    proc.artifact_dir = artifact_dir  # type: ignore[attr-defined]
    return proc


# Stacks present for hml with SKIP_DATABRICKS=true (module basenames terraform sees):
#   vpc -> 02_vpc, peripherals -> 04_peripherals, iam -> 03_iam, ecs -> 07_ecs
def _seed_all_no_change_plans(artifact_dir: Path) -> None:
    for sid in ("vpc", "peripherals", "iam", "ecs"):
        _stage_approved_plan(artifact_dir, sid, has_changes=False)


def test_upstream_unchanged_applies_saved_plan(tmp_path: Path) -> None:
    """vpc has a saved plan with changes, upstreams=[] -> applies the SAVED tfplan
    binary, NOT a freshly re-planned one. terraform plan is NOT consulted for it."""
    artifact_dir = tmp_path / ".plan-artifacts"
    _seed_all_no_change_plans(artifact_dir)
    _stage_approved_plan(artifact_dir, "vpc", has_changes=True)
    # vpc's saved plan binary must be the file applied:
    proc = _run(tmp_path, {})
    assert proc.returncode == 0, proc.stderr
    log = proc.apply_log  # type: ignore[attr-defined]
    # The applied plan arg for 02_vpc must be the absolute path into .plan-artifacts/vpc
    assert "02_vpc" in log
    vpc_line = next(ln for ln in log.splitlines() if ln.startswith("02_vpc "))
    assert str(artifact_dir / "vpc" / "tfplan") in vpc_line, vpc_line


def test_replan_diff_match_applies_fresh_plan(tmp_path: Path) -> None:
    """vpc applies a change in-run; ecs (upstreams=[vpc]) is therefore RE-PLANNED. Its
    re-plan matches its approved summary (both 1-add) -> apply proceeds against the
    FRESH tfplan, not the saved binary."""
    artifact_dir = tmp_path / ".plan-artifacts"
    _seed_all_no_change_plans(artifact_dir)
    _stage_approved_plan(artifact_dir, "vpc", has_changes=True)
    _stage_approved_plan(artifact_dir, "ecs", has_changes=True)
    proc = _run(tmp_path, {"TF_PLAN_CHANGED_STACKS": "07_ecs"})
    assert proc.returncode == 0, proc.stderr
    log = proc.apply_log  # type: ignore[attr-defined]
    ecs_line = next(ln for ln in log.splitlines() if ln.startswith("07_ecs "))
    # fresh re-plan tfplan is the relative "tfplan" in the module dir, NOT the artifact path
    assert ecs_line.strip() == "07_ecs tfplan", ecs_line
    assert str(artifact_dir / "ecs" / "tfplan") not in ecs_line


def test_replan_diff_divergence_fails_closed(tmp_path: Path) -> None:
    """vpc applies in-run -> ecs re-planned. The approved ecs summary was 1-add but the
    re-plan now returns NO changes -> DIVERGENCE -> fail closed (exit 3), diff published,
    ecs NOT applied."""
    artifact_dir = tmp_path / ".plan-artifacts"
    _seed_all_no_change_plans(artifact_dir)
    _stage_approved_plan(artifact_dir, "vpc", has_changes=True)
    _stage_approved_plan(artifact_dir, "ecs", has_changes=True)  # approved = 1 add
    # ecs re-plan returns no changes (07_ecs NOT in changed list) -> diverges from approved
    proc = _run(tmp_path, {"TF_PLAN_CHANGED_STACKS": ""})
    assert proc.returncode == 3, (proc.returncode, proc.stdout, proc.stderr)
    div_file = proc.div_dir / "ecs.diff.txt"  # type: ignore[attr-defined]
    assert div_file.exists(), "divergence diff must be published as an artifact"
    log = proc.apply_log  # type: ignore[attr-defined]
    assert "07_ecs" not in log, "ecs must NOT be applied on divergence"


def test_no_saved_plan_replans_and_gates(tmp_path: Path) -> None:
    """A stack with NO saved approved plan (artifact absent) is re-planned and gated.
    With no approved plan, plan_gate_check.sh plan-diff fails closed (exit 3) unless the
    re-plan is itself a no-op. Here ecs has no saved plan and re-plans WITH changes ->
    diverges (missing approved) -> fail closed."""
    artifact_dir = tmp_path / ".plan-artifacts"
    for sid in ("vpc", "peripherals", "iam"):
        _stage_approved_plan(artifact_dir, sid, has_changes=False)
    # ecs: no artifact staged at all
    proc = _run(tmp_path, {"TF_PLAN_CHANGED_STACKS": "07_ecs"})
    assert proc.returncode == 3, (proc.returncode, proc.stdout, proc.stderr)
    log = proc.apply_log  # type: ignore[attr-defined]
    assert "07_ecs" not in log


def test_deploy_order_matches_stack_map(tmp_path: Path) -> None:
    """deploy_env.sh iterates stacks in the map's declared order (F-QA-A1-3): no
    hardcoded stack list. All no-change -> nothing applied, exit 0, and every map stack
    (minus skipped databricks) is visited in order in the run log."""
    artifact_dir = tmp_path / ".plan-artifacts"
    _seed_all_no_change_plans(artifact_dir)
    proc = _run(tmp_path, {})
    assert proc.returncode == 0, proc.stderr
    data = json.loads((CI_DIR / "stack_map.json").read_text())
    expected_paths = [
        s["path"].split("/")[-1]
        for s in data["environments"]["hml"]["stacks"]
        if not s["id"].startswith("databricks")
    ]
    seen = [
        ln.split()[-1].rsplit("/", 1)[-1].replace(")", "")
        for ln in proc.stdout.splitlines()
        if ln.strip().startswith("DIR:")
    ]
    # every expected stack dir appears, in declared order
    idxs = [seen.index(p) for p in expected_paths]
    assert idxs == sorted(idxs), (expected_paths, seen)
"""Hermetic — no real venv, no AWS, no network. Run: pytest -p no:cacheprovider"""
