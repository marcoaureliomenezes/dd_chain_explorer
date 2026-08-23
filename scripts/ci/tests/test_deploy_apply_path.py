"""Hermetic apply-path tests for scripts/ci/deploy_env.sh (T-R6-A2(b), ADR-R6-5, F-01).

Proves the post-gate apply phase ALWAYS RE-PLANS under the deploy role and NEVER
consumes a saved `tfplan` BINARY artifact (F-01, public-repo CI security audit,
2026-08-23 — a tfplan binary embeds TF_VAR_* secret values in plaintext and GitHub
Actions artifacts on a public repo are world-downloadable):

  * every stack -> RE-PLANNED locally and gated against the approved plan.txt TEXT
    summary via plan_gate_check.sh plan-diff; matching re-plan applies the FRESH
    tfplan, DIVERGING re-plan FAILS CLOSED (exit 3) with a published divergence diff;
  * the approved-plan artifact staged/downloaded in these tests carries ONLY plan.txt
    (no tfplan binary — mirrors what plan_env.sh now stages and the workflow now
    uploads with retention-days: 1).

terraform and aws are mocked by stub binaries on PATH (no real cloud, no real venv).
Tests run prd (T-A.8 survivor set): tf_state, iam, peripherals, lambda
(lambda.upstreams=[peripherals] — the one real same-env dependency edge that survives
T-B.2/T-B.3, per scripts/ci/stack_map.json). Hermetic; run with `-p no:cacheprovider`.
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


def _stage_approved_plan(artifact_dir: Path, sid: str, *, has_changes: bool) -> None:
    """Write a saved pre-gate plan summary for a stack — plan.txt ONLY (F-01): the
    real plan_env.sh no longer stages a tfplan binary, and deploy_env.sh must never
    look for one."""
    sdir = artifact_dir / sid
    sdir.mkdir(parents=True, exist_ok=True)
    if has_changes:
        (sdir / "plan.txt").write_text(
            "  # aws_s3_bucket.x will be created\nPlan: 1 to add, 0 to change, 0 to destroy.\n"
        )
    else:
        (sdir / "plan.txt").write_text("No changes. Your infrastructure matches the configuration.\n")


def _run(tmp_path: Path, env_extra: dict[str, str]) -> subprocess.CompletedProcess:
    bindir = _make_bindir(tmp_path)
    artifact_dir = tmp_path / ".plan-artifacts"
    div_dir = tmp_path / ".plan-divergence"
    apply_log = tmp_path / "apply.log"
    apply_log.touch()
    env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "PLAN_ARTIFACT_DIR": str(artifact_dir),
        "DIVERGENCE_DIR": str(div_dir),
        "TF_APPLY_LOG": str(apply_log),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
        "GITHUB_OUTPUT": str(tmp_path / "gh_output"),
    }
    env.update(env_extra)
    proc = subprocess.run(
        ["bash", str(DEPLOY_ENV), "prd"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    proc.apply_log = apply_log.read_text() if apply_log.exists() else ""  # type: ignore[attr-defined]
    proc.div_dir = div_dir  # type: ignore[attr-defined]
    proc.artifact_dir = artifact_dir  # type: ignore[attr-defined]
    # deploy_hml cds into the REAL services/<env>/<stack> module dirs and tf_plan.sh
    # writes plan.txt + tfplan.haschanges there. Those are throwaway plan artifacts and
    # MUST NOT be left inside the repo working tree (services/** must stay clean). Remove
    # any the run produced under services/.
    for leak in REPO_ROOT.joinpath("services").rglob("plan.txt"):
        leak.unlink(missing_ok=True)
    for leak in REPO_ROOT.joinpath("services").rglob("tfplan.haschanges"):
        leak.unlink(missing_ok=True)
    for leak in REPO_ROOT.joinpath("services").rglob("tfplan"):
        if leak.is_file():
            leak.unlink(missing_ok=True)
    return proc


# Stacks present for prd (module basenames terraform sees, T-A.8 survivor set):
#   tf_state -> 01_tf_state, iam -> 03_iam, peripherals -> 04_peripherals, lambda -> 06_lambda
# bootstrap (00_bootstrap) is operator_only -> excluded from deploy_env.sh's loop by
# scripts/ci/stack_list.sh (T-A.8) and never appears here.
def _seed_all_no_change_plans(artifact_dir: Path) -> None:
    for sid in ("tf_state", "iam", "peripherals", "lambda"):
        _stage_approved_plan(artifact_dir, sid, has_changes=False)


def test_upstream_unchanged_replans_and_applies_matching_plan(tmp_path: Path) -> None:
    """peripherals has an approved plan.txt with changes, upstreams=[]. F-01: there is
    no saved tfplan binary to consume, so it is ALWAYS re-planned; its re-plan matches
    the approved summary (both 1-add) -> apply proceeds against the FRESH tfplan
    produced locally, never a path under .plan-artifacts/."""
    artifact_dir = tmp_path / ".plan-artifacts"
    _seed_all_no_change_plans(artifact_dir)
    _stage_approved_plan(artifact_dir, "peripherals", has_changes=True)
    assert not (artifact_dir / "peripherals" / "tfplan").exists()
    proc = _run(tmp_path, {"TF_PLAN_CHANGED_STACKS": "04_peripherals"})
    assert proc.returncode == 0, proc.stderr
    log = proc.apply_log  # type: ignore[attr-defined]
    assert "04_peripherals" in log
    peripherals_line = next(ln for ln in log.splitlines() if ln.startswith("04_peripherals "))
    # The applied plan arg is the fresh relative "tfplan" produced by THIS re-plan,
    # never a path into .plan-artifacts/ (no binary is ever staged there any more).
    assert peripherals_line.strip() == "04_peripherals tfplan", peripherals_line
    assert str(artifact_dir) not in peripherals_line


def test_replan_diff_match_applies_fresh_plan(tmp_path: Path) -> None:
    """peripherals and lambda (upstreams=[peripherals]) both re-plan matching their
    approved 1-add summaries -> both apply against their FRESH tfplan, never a saved
    binary (none exists — F-01)."""
    artifact_dir = tmp_path / ".plan-artifacts"
    _seed_all_no_change_plans(artifact_dir)
    _stage_approved_plan(artifact_dir, "peripherals", has_changes=True)
    _stage_approved_plan(artifact_dir, "lambda", has_changes=True)
    proc = _run(tmp_path, {"TF_PLAN_CHANGED_STACKS": "04_peripherals 06_lambda"})
    assert proc.returncode == 0, proc.stderr
    log = proc.apply_log  # type: ignore[attr-defined]
    lambda_line = next(ln for ln in log.splitlines() if ln.startswith("06_lambda "))
    # fresh re-plan tfplan is the relative "tfplan" in the module dir, NOT the artifact path
    assert lambda_line.strip() == "06_lambda tfplan", lambda_line
    assert str(artifact_dir / "lambda") not in lambda_line


def test_replan_diff_divergence_fails_closed(tmp_path: Path) -> None:
    """peripherals re-plans matching its approved summary and applies in-run -> lambda
    (upstreams=[peripherals]) is re-planned. The approved lambda summary was 1-add but
    the re-plan now returns NO changes -> DIVERGENCE -> fail closed (exit 3), diff
    published, lambda NOT applied."""
    artifact_dir = tmp_path / ".plan-artifacts"
    _seed_all_no_change_plans(artifact_dir)
    _stage_approved_plan(artifact_dir, "peripherals", has_changes=True)
    _stage_approved_plan(artifact_dir, "lambda", has_changes=True)  # approved = 1 add
    # peripherals re-plans matching (1 add); lambda re-plan returns no changes
    # (06_lambda NOT in changed list) -> diverges from its approved 1-add summary.
    proc = _run(tmp_path, {"TF_PLAN_CHANGED_STACKS": "04_peripherals"})
    assert proc.returncode == 3, (proc.returncode, proc.stdout, proc.stderr)
    div_file = proc.div_dir / "lambda.diff.txt"  # type: ignore[attr-defined]
    assert div_file.exists(), "divergence diff must be published as an artifact"
    log = proc.apply_log  # type: ignore[attr-defined]
    assert "06_lambda" not in log, "lambda must NOT be applied on divergence"


def test_no_saved_plan_replans_and_gates(tmp_path: Path) -> None:
    """A stack with NO saved approved plan (artifact absent) is re-planned and gated.
    With no approved plan, plan_gate_check.sh plan-diff fails closed (exit 3) unless the
    re-plan is itself a no-op. Here lambda has no saved plan and re-plans WITH changes ->
    diverges (missing approved) -> fail closed."""
    artifact_dir = tmp_path / ".plan-artifacts"
    for sid in ("tf_state", "iam", "peripherals"):
        _stage_approved_plan(artifact_dir, sid, has_changes=False)
    # lambda: no artifact staged at all
    proc = _run(tmp_path, {"TF_PLAN_CHANGED_STACKS": "06_lambda"})
    assert proc.returncode == 3, (proc.returncode, proc.stdout, proc.stderr)
    log = proc.apply_log  # type: ignore[attr-defined]
    assert "06_lambda" not in log


def _run_replan_diff(
    tmp_path: Path,
    *,
    deferred: bool,
    approved_present: bool,
    replan_changes: bool,
    destroy_ack: str = "false",
    destroys: bool = False,
) -> subprocess.CompletedProcess:
    """Source deploy_env.sh and drive deploy_stack_replan_diff for the prd 05b
    (databricks_workspace) deferred stack in isolation (F-QA-A1R-2). The terraform stub
    plans 05b's module dir; whether it has changes/destroys is shaped per call."""
    bindir = _make_bindir(tmp_path)
    artifact_dir = tmp_path / ".plan-artifacts"
    artifact_dir.mkdir()
    apply_log = tmp_path / "apply.log"
    apply_log.touch()
    approved_txt = artifact_dir / "databricks_workspace" / "plan.txt"
    if approved_present:
        approved_txt.parent.mkdir(parents=True, exist_ok=True)
        approved_txt.write_text("No changes. Your infrastructure matches the configuration.\n")

    # A terraform stub for the 05b module: plan emits changes/destroys per flags.
    if not replan_changes:
        plan_echo = 'echo "No changes. Your infrastructure matches the configuration."'
        plan_exit = "0"
    elif destroys:
        plan_echo = 'echo "  # aws_x.y will be destroyed"; echo "Plan: 0 to add, 0 to change, 1 to destroy."'
        plan_exit = "2"
    else:
        plan_echo = 'echo "  # aws_x.y will be created"; echo "Plan: 1 to add, 0 to change, 0 to destroy."'
        plan_exit = "2"
    stub = f"""#!/usr/bin/env bash
set -u
case "${{1:-}}" in
  init|validate|output) exit 0 ;;
  plan)
    out_file="tfplan"
    for a in "$@"; do case "$a" in -out=*) out_file="${{a#-out=}}";; esac; done
    : > "$out_file"
    {plan_echo}
    exit {plan_exit} ;;
  apply) echo "05b_databricks_workspace ${{!#}}" >> "${{TF_APPLY_LOG:-/dev/null}}"; exit 0 ;;
  *) exit 0 ;;
esac
"""
    (bindir / "terraform").write_text(stub)
    (bindir / "terraform").chmod(0o755)

    # Operate in a throwaway module dir (init/validate/plan are stubbed, so real .tf is
    # not needed) — keeps tfplan/plan.txt OUT of services/** (no artifact leak).
    module_dir = tmp_path / "module"
    module_dir.mkdir()
    harness = f"""
set -euo pipefail
export DEPLOY_ENV_SOURCE_ONLY=1
export PLAN_ARTIFACT_DIR={artifact_dir!s}
export DIVERGENCE_DIR={tmp_path / ".plan-divergence"!s}
export TF_APPLY_LOG={apply_log!s}
export DESTROY_ACK={destroy_ack}
export GITHUB_STEP_SUMMARY={tmp_path / "summary.md"!s}
# shellcheck disable=SC1090
source {DEPLOY_ENV!s} prd
cd {module_dir!s}
deploy_stack_replan_diff databricks_workspace "PRD/DatabricksWorkspace" \
  "{approved_txt!s}" {"true" if deferred else "false"}
"""
    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}"}
    proc = subprocess.run(
        ["bash", "-c", harness],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    proc.apply_log = apply_log.read_text()  # type: ignore[attr-defined]
    return proc


def test_deferred_missing_approved_noop_takes_deferred_path(tmp_path: Path) -> None:
    """05b is declared-deferred; with no approved plan and a no-op re-plan, the deferred
    path lets the run proceed (exit 0) — NOT the unconditional exit 3 of F-QA-A1R-2."""
    proc = _run_replan_diff(tmp_path, deferred=True, approved_present=False, replan_changes=False)
    assert proc.returncode == 0, (proc.stdout, proc.stderr)


def test_deferred_missing_approved_with_changes_applies(tmp_path: Path) -> None:
    """Deferred 05b with changes (no destroys): informed post-gate re-plan applies."""
    proc = _run_replan_diff(tmp_path, deferred=True, approved_present=False, replan_changes=True)
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert "05b_databricks_workspace tfplan" in proc.apply_log  # type: ignore[attr-defined]


def test_deferred_missing_approved_destroy_without_ack_fails(tmp_path: Path) -> None:
    """The deferred path still runs destroy-ack: a destroying re-plan without ack stops."""
    proc = _run_replan_diff(
        tmp_path,
        deferred=True,
        approved_present=False,
        replan_changes=True,
        destroys=True,
        destroy_ack="false",
    )
    assert proc.returncode == 2, (proc.returncode, proc.stdout, proc.stderr)
    assert "05b_databricks_workspace" not in proc.apply_log  # type: ignore[attr-defined]


def test_nondeferred_missing_approved_fails_closed(tmp_path: Path) -> None:
    """A NON-deferred stack missing its approved plan fails closed (exit 3) even via the
    sourced apply path — the fail-closed contract is preserved for non-deferred stacks."""
    proc = _run_replan_diff(tmp_path, deferred=False, approved_present=False, replan_changes=True)
    assert proc.returncode == 3, (proc.returncode, proc.stdout, proc.stderr)


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
        for s in data["environments"]["prd"]["stacks"]
        if not s.get("operator_only", False)
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
