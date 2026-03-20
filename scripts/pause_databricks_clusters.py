#!/usr/bin/env python3
"""
scripts/pause_databricks_clusters.py

Terminates all RUNNING interactive clusters in the Databricks PROD workspace
and saves their IDs/names to a state file so `resume_databricks_clusters.py`
can restart exactly the same set.

Auth: reads ~/.databrickscfg [prd] (host + token).
      The profile must point to a WORKSPACE URL (not accounts.cloud.databricks.com).

State file: ~/.cache/dd-chain-explorer-standby.json

Usage:
    python scripts/pause_databricks_clusters.py [--profile prd] [--dry-run]
"""

import argparse
import configparser
import json
import os
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("ERROR: 'requests' library not found. Run: pip install requests")


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_profile(profile: str) -> tuple[str, str]:
    """Read host and token from ~/.databrickscfg for the given profile."""
    cfg_path = Path.home() / ".databrickscfg"
    if not cfg_path.exists():
        sys.exit(f"ERROR: ~/.databrickscfg not found. Run: databricks configure --profile {profile}")

    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)

    if profile not in cfg:
        sys.exit(
            f"ERROR: Profile [{profile}] not found in ~/.databrickscfg.\n"
            f"       Available profiles: {list(cfg.sections())}\n"
            f"       Run: databricks configure --profile {profile}"
        )

    host = cfg[profile].get("host", "").rstrip("/")
    token = cfg[profile].get("token", "")

    if not host or not token:
        sys.exit(
            f"ERROR: Profile [{profile}] is missing 'host' or 'token'.\n"
            f"       Re-run: databricks configure --profile {profile}"
        )

    if "accounts.cloud.databricks.com" in host:
        sys.exit(
            f"ERROR: Profile [{profile}] points to the ACCOUNT-LEVEL URL ({host}).\n"
            f"       For cluster operations you need a WORKSPACE URL, e.g.\n"
            f"       https://<workspace-id>.azuredatabricks.net  or\n"
            f"       https://dbc-<id>.cloud.databricks.com\n"
            f"       Re-run: databricks configure --profile {profile}"
        )

    return host, token


def state_file_path() -> Path:
    cache_dir = Path.home() / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "dd-chain-explorer-standby.json"


# ---------------------------------------------------------------------------
# Databricks REST helpers
# ---------------------------------------------------------------------------

def db_get(host: str, token: str, path: str) -> dict:
    resp = requests.get(
        f"{host}/api/2.0{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def db_post(host: str, token: str, path: str, payload: dict) -> dict:
    resp = requests.post(
        f"{host}/api/2.0{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Cluster filter: interactive clusters only (source = UI or API, not JOB/PIPELINE)
# ---------------------------------------------------------------------------

INTERACTIVE_SOURCES = {"UI", "API"}
RUNNING_STATES = {"RUNNING", "RESIZING"}


def list_interactive_running(host: str, token: str) -> list[dict]:
    data = db_get(host, token, "/clusters/list")
    clusters = data.get("clusters", [])
    return [
        c for c in clusters
        if c.get("cluster_source", "UI") in INTERACTIVE_SOURCES
        and c.get("state", "") in RUNNING_STATES
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Pause Databricks PROD interactive clusters.")
    parser.add_argument("--profile", default="prd", help="~/.databrickscfg profile (default: prd)")
    parser.add_argument("--dry-run", action="store_true", help="List clusters without terminating")
    args = parser.parse_args()

    host, token = load_profile(args.profile)
    print(f"\n=== Databricks Cluster Pause (profile: [{args.profile}]) ===")
    print(f"Workspace: {host}\n")

    running_clusters = list_interactive_running(host, token)

    if not running_clusters:
        print("No RUNNING interactive clusters found — nothing to pause.")
        print("(Job clusters and DLT pipelines are managed by Databricks automatically.)")
        return

    print(f"Found {len(running_clusters)} RUNNING interactive cluster(s):")
    for c in running_clusters:
        print(f"  [{c.get('state')}] {c['cluster_id']}  {c.get('cluster_name', '<no name>')}")

    if args.dry_run:
        print("\n[DRY RUN] No clusters terminated.")
        return

    print()
    paused = []
    for c in running_clusters:
        cluster_id = c["cluster_id"]
        cluster_name = c.get("cluster_name", "<no name>")
        try:
            db_post(host, token, "/clusters/delete", {"cluster_id": cluster_id})
            print(f"  [OK] Terminated: {cluster_name} ({cluster_id})")
            paused.append({
                "cluster_id": cluster_id,
                "cluster_name": cluster_name,
                "state_before": c.get("state"),
                "paused_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
        except requests.HTTPError as exc:
            print(f"  [WARN] Could not terminate {cluster_name} ({cluster_id}): {exc}")

    state_path = state_file_path()
    state_path.write_text(json.dumps({"clusters": paused}, indent=2))
    print(f"\nState saved → {state_path}")
    print(f"Paused {len(paused)}/{len(running_clusters)} cluster(s).")
    print("\nRun 'make prod_resume' to restart these clusters.")


if __name__ == "__main__":
    main()
