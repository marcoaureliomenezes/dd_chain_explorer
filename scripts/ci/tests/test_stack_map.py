"""Integrity tests for scripts/ci/stack_map.json — the single-source stack map.

Enforces F-ARCH-4 (T-R6-A2(g) / T-R6-A8(a)): the stack list + dependency declarations
live in ONE data-driven file; stack module paths exist; upstreams reference declared
stacks only; no dependency cycles.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

CI_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = CI_DIR.parents[1]
MAP_PATH = CI_DIR / "stack_map.json"


def _load() -> dict:
    return json.loads(MAP_PATH.read_text())


def _load_changed_stacks():
    spec = importlib.util.spec_from_file_location(
        "changed_stacks", CI_DIR / "changed_stacks.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_map_is_valid_json_with_environments() -> None:
    data = _load()
    assert set(data["environments"]) >= {"dev", "hml", "prd"}


def test_every_stack_path_exists_on_disk() -> None:
    data = _load()
    missing = []
    for env, env_block in data["environments"].items():
        for stack in env_block["stacks"]:
            p = REPO_ROOT / stack["path"]
            if not p.is_dir():
                missing.append(f"{env}/{stack['id']} -> {stack['path']}")
    assert not missing, f"stack paths absent: {missing}"


def test_upstreams_reference_declared_stacks() -> None:
    data = _load()
    bad = []
    for env, env_block in data["environments"].items():
        ids = {s["id"] for s in env_block["stacks"]}
        for stack in env_block["stacks"]:
            for up in stack.get("upstreams", []):
                if up not in ids:
                    bad.append(f"{env}/{stack['id']} upstream '{up}' not declared")
    assert not bad, bad


def test_no_dependency_cycles() -> None:
    data = _load()
    for env, env_block in data["environments"].items():
        deps = {s["id"]: list(s.get("upstreams", [])) for s in env_block["stacks"]}

        visiting: set[str] = set()
        done: set[str] = set()

        def visit(node: str, path: list[str]) -> None:
            if node in done:
                return
            assert node not in visiting, f"{env}: cycle through {path + [node]}"
            visiting.add(node)
            for up in deps.get(node, []):
                visit(up, path + [node])
            visiting.discard(node)
            done.add(node)

        for sid in deps:
            visit(sid, [])


def test_bootstrap_nonplannable_only_for_workspace_stacks() -> None:
    """05b (databricks_workspace) is the canonical deferred stack; assert it is the
    one marked non-bootstrap-plannable (its upstream output exists only post-apply)."""
    data = _load()
    for env in ("hml", "prd"):
        for stack in data["environments"][env]["stacks"]:
            if stack["id"] == "databricks_workspace":
                assert stack["bootstrap_plannable"] is False
            else:
                assert stack["bootstrap_plannable"] is True


def test_declared_modules_exist_on_disk() -> None:
    """Every module a stack declares must exist under services/modules/<m>/ — the
    module-edit -> dependent-stack map (T-R6-A8) is only sound if its edges resolve."""
    data = _load()
    missing = []
    for env, env_block in data["environments"].items():
        for stack in env_block["stacks"]:
            for m in stack.get("modules", []):
                if not (REPO_ROOT / "services" / "modules" / m).is_dir():
                    missing.append(f"{env}/{stack['id']} -> modules/{m}")
    assert not missing, f"declared modules absent: {missing}"


# ── change-detection (T-R6-A8): module edit -> only dependent stacks ──────────

def test_stack_own_path_edit_triggers_only_that_stack() -> None:
    cs = _load_changed_stacks()
    stacks = {s["id"]: s for s in cs.stacks_for_env("prd")}
    changed = ["services/prd/02_vpc/main.tf"]
    assert cs.stack_is_changed(stacks["vpc"], changed) is True
    assert cs.stack_is_changed(stacks["iam"], changed) is False


def test_module_edit_triggers_only_consuming_stacks() -> None:
    """A services/modules/iam edit triggers stacks that DECLARE iam, never every
    stack (the old blanket ^services/modules/ behaviour, CI-H3)."""
    cs = _load_changed_stacks()
    stacks = {s["id"]: s for s in cs.stacks_for_env("prd")}
    changed = ["services/modules/iam/main.tf"]
    # iam stack declares modules:["iam"] -> changed
    assert cs.stack_is_changed(stacks["iam"], changed) is True
    # vpc stack declares modules:["vpc"] -> NOT changed by an iam module edit
    assert cs.stack_is_changed(stacks["vpc"], changed) is False
    # peripherals declares s3/dynamodb/... but not iam -> NOT changed
    assert cs.stack_is_changed(stacks["peripherals"], changed) is False


def test_module_edit_with_multiple_consumers() -> None:
    cs = _load_changed_stacks()
    stacks = {s["id"]: s for s in cs.stacks_for_env("prd")}
    # peripherals declares s3; only it (of prd stacks) consumes s3.
    changed = ["services/modules/s3/outputs.tf"]
    assert cs.stack_is_changed(stacks["peripherals"], changed) is True
    assert cs.stack_is_changed(stacks["vpc"], changed) is False


def test_unrelated_edit_triggers_no_stack() -> None:
    cs = _load_changed_stacks()
    changed = ["README.md", "scripts/ci/changed_stacks.py"]
    for stack in cs.stacks_for_env("prd"):
        assert cs.stack_is_changed(stack, changed) is False


def test_dev_stacks_have_no_module_edges() -> None:
    """DEV stacks consume no shared services/modules — a module edit must not
    trigger any DEV stack (only an own-path edit does)."""
    cs = _load_changed_stacks()
    changed = ["services/modules/vpc/main.tf"]
    for stack in cs.stacks_for_env("dev"):
        assert cs.stack_is_changed(stack, changed) is False
