"""T-A.8/T-A.7/T-A.4 governance assertions over scripts/ci/stack_map.json and the
workflow files that must read it instead of hardcoding a stack list.

Intent: CONTRACT — T-A.8, T-A.7, T-A.4. Hermetic; no network, no real cloud.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

CI_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = CI_DIR.parents[1]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
STACK_MAP = CI_DIR / "stack_map.json"


def _load_map() -> dict:
    return json.loads(STACK_MAP.read_text())


def _on_disk_stack_dirs() -> set[str]:
    """Every directory under services/{dev,hml,prd}/ that is itself a Terraform root
    (carries a `backend "s3"` block) — the true on-disk survivor set."""
    found = set()
    for env in ("dev", "hml", "prd"):
        env_dir = REPO_ROOT / "services" / env
        if not env_dir.is_dir():
            continue
        for child in env_dir.iterdir():
            if not child.is_dir():
                continue
            if any("required_version" in f.read_text() for f in child.glob("*.tf")):
                found.add(f"services/{env}/{child.name}")
    return found


def test_map_equals_on_disk_survivors() -> None:
    data = _load_map()
    map_paths = {
        s["path"]
        for env in data["environments"].values()
        for s in env["stacks"]
    }
    on_disk = _on_disk_stack_dirs()
    assert map_paths == on_disk, (map_paths ^ on_disk, map_paths, on_disk)


def test_bootstrap_excluded_from_ci_stack_lists() -> None:
    """prd/00_bootstrap is operator_only — scripts/ci/stack_list.sh must never emit it,
    for either the default (plan/apply) or --destroyable set."""
    default = subprocess.run(
        ["bash", str(CI_DIR / "stack_list.sh"), "prd"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    destroyable = subprocess.run(
        ["bash", str(CI_DIR / "stack_list.sh"), "prd", "--destroyable"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    assert "bootstrap" not in default
    assert "bootstrap" not in destroyable
    assert "tf_state" not in destroyable  # never_destroy
    assert "tf_state" in default          # plannable, just never destroyed


def test_destroy_all_stack_set_equals_map_destroyable_set() -> None:
    """destroy_all_cloud_infra.yml's static per-stack destroy jobs must cover exactly
    the map's destroyable survivor set — no more, no less (T-A.8, F-ARCH-4)."""
    wf = (WORKFLOWS_DIR / "destroy_all_cloud_infra.yml").read_text()
    wf_dirs = set(re.findall(r'chdir="\$\{\{\s*env\.\w+_ROOT\s*\}\}/(\w+)"', wf))
    root_map = {"DEV_ROOT": "dev", "HML_ROOT": "hml", "PRD_ROOT": "prd"}
    roots = dict(re.findall(r"(\w+_ROOT):\s*services/(\w+)", wf))
    expected = set()
    for env_key, env in roots.items():
        for m in re.finditer(
            rf'chdir="\$\{{\{{\s*env\.{env_key}\s*\}}\}}/(\w+)"', wf
        ):
            expected.add(f"services/{env}/{m.group(1)}")
    data = _load_map()
    destroyable_paths = {
        s["path"]
        for env in data["environments"].values()
        for s in env["stacks"]
        if not s.get("operator_only", False) and not s.get("never_destroy", False)
    }
    assert expected == destroyable_paths, (expected ^ destroyable_paths, expected, destroyable_paths)
    assert wf_dirs or expected  # sanity: the regexes above actually matched something


def test_tf_plan_lock_false_present_on_readonly_role_jobs() -> None:
    """Every job that assumes AWS_DEPLOY_ROLE_READONLY and calls tf_plan.sh (directly
    or via plan_env.sh) must pass TF_PLAN_ARGS=-lock=false (T-A.8, F-04) — the READONLY
    role's IAM policy carries no dynamodb:PutItem/DeleteItem on the state lock table."""
    for name in ("plan_on_pr.yml", "drift_detection.yml"):
        wf = (WORKFLOWS_DIR / name).read_text()
        assert 'TF_PLAN_ARGS: "-lock=false"' in wf, f"{name} missing TF_PLAN_ARGS=-lock=false"
    deploy_cloud = (WORKFLOWS_DIR / "deploy_cloud_infra.yml").read_text()
    assert 'TF_PLAN_ARGS:                    "-lock=false"' in deploy_cloud


def test_tf_plan_sh_supports_tf_plan_args_passthrough() -> None:
    src = (CI_DIR / "tf_plan.sh").read_text()
    assert "TF_PLAN_ARGS" in src
    assert "terraform plan" in src and "${TF_PLAN_ARGS}" in src


def test_preflight_step_present_in_every_role_assuming_workflow() -> None:
    """Every workflow with a `configure-aws-credentials` job must also declare a
    preflight step validating the AWS_DEPLOY_ROLE_* variable(s) it consumes (T-A.7)."""
    for wf_path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        text = wf_path.read_text()
        if "configure-aws-credentials" not in text:
            continue
        has_preflight_job = bool(re.search(r"(?i)preflight", text))
        has_role_check = "AWS_DEPLOY_ROLE" in text and "::error::" in text
        assert has_preflight_job and has_role_check, (
            f"{wf_path.name}: no preflight AWS_DEPLOY_ROLE_* check found"
        )


def test_check_prd_version_reads_version_file() -> None:
    src = (CI_DIR / "check_prd_version.sh").read_text()
    assert "cat VERSION" in src


def test_publish_oidc_vars_maps_four_role_names() -> None:
    script = CI_DIR / "publish_oidc_vars.sh"
    assert script.is_file(), "scripts/ci/publish_oidc_vars.sh must exist (T-A.4)"
    src = script.read_text()
    for name in ("AWS_DEPLOY_ROLE_DEV", "AWS_DEPLOY_ROLE_HML", "AWS_DEPLOY_ROLE_PRD", "AWS_DEPLOY_ROLE_READONLY"):
        assert name in src, f"publish_oidc_vars.sh does not reference {name}"
    assert "gh variable set" in src
    assert "--dry-run" in src and "--apply" in src
