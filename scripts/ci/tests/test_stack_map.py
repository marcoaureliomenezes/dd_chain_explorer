"""Integrity tests for scripts/ci/stack_map.json — the single-source stack map.

Enforces F-ARCH-4 (T-R6-A2(g) / T-R6-A8(a)): the stack list + dependency declarations
live in ONE data-driven file; stack module paths exist; upstreams reference declared
stacks only; no dependency cycles.
"""

from __future__ import annotations

import json
from pathlib import Path

CI_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = CI_DIR.parents[1]
MAP_PATH = CI_DIR / "stack_map.json"


def _load() -> dict:
    return json.loads(MAP_PATH.read_text())


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
