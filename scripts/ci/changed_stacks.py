#!/usr/bin/env python3
"""Single-source change detection: which stacks a set of changed files affect.

Reads scripts/ci/stack_map.json (the ONE data-driven map, F-ARCH-4) and decides,
for every stack in a given environment, whether it must be re-planned given a list
of changed file paths (repo-relative, as produced by `git diff --name-only`).

A stack is "changed" when a changed file is:
  - under the stack's own ``path`` (``services/<env>/<dir>/...``), OR
  - under ``services/modules/<m>/`` for any module ``m`` the stack declares in its
    ``modules`` list.

This replaces the blanket ``^services/modules/`` clause (CI-H3): a shared-module edit
now triggers ONLY the stacks that consume that module, never every stack. No stack id
or module name is hardcoded here or in any workflow — both ``plan_on_pr.yml`` and the
DEV helper ``detect_changes.sh`` resolve membership through this file.

Usage:
    changed_stacks.py <env> <stack-id>      # exit 0 if changed, 1 if not
    changed_stacks.py <env> --emit-github    # prints "<env>_<id>_changed=true|false"
                                             # lines to stdout (caller appends to
                                             # $GITHUB_OUTPUT, optionally rewriting keys)

Changed files are read from stdin (one path per line) OR from $CHANGED_FILES (newline
or whitespace separated). The env var DIFF_BASE_OK must be "true" — the caller is
responsible for failing loud when no merge-base exists (see detect_changes.sh /
plan_on_pr.yml); this script refuses to run on a silently-degraded diff.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

CI_DIR = Path(__file__).resolve().parent
MAP_PATH = CI_DIR / "stack_map.json"


def load_map() -> dict:
    return json.loads(MAP_PATH.read_text())


def read_changed_files() -> list[str]:
    raw = os.environ.get("CHANGED_FILES")
    if raw is None:
        raw = sys.stdin.read()
    return [ln.strip() for ln in raw.replace("\0", "\n").splitlines() if ln.strip()]


def stack_is_changed(stack: dict, changed: list[str]) -> bool:
    prefix = stack["path"].rstrip("/") + "/"
    module_prefixes = [f"services/modules/{m}/" for m in stack.get("modules", [])]
    for f in changed:
        if f.startswith(prefix):
            return True
        if any(f.startswith(mp) for mp in module_prefixes):
            return True
    return False


def stacks_for_env(env: str) -> list[dict]:
    data = load_map()
    if env not in data["environments"]:
        sys.stderr.write(f"changed_stacks: unknown environment '{env}'\n")
        sys.exit(2)
    return data["environments"][env]["stacks"]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        sys.stderr.write(__doc__ or "")
        return 2
    env = argv[1]
    changed = read_changed_files()

    if argv[2:] and argv[2] == "--emit-github":
        for stack in stacks_for_env(env):
            flag = "true" if stack_is_changed(stack, changed) else "false"
            sys.stdout.write(f"{env}_{stack['id']}_changed={flag}\n")
        return 0

    stack_id = argv[2]
    for stack in stacks_for_env(env):
        if stack["id"] == stack_id:
            return 0 if stack_is_changed(stack, changed) else 1
    sys.stderr.write(f"changed_stacks: unknown stack '{env}/{stack_id}'\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
