#!/usr/bin/env python3
"""
scripts/resume_databricks_clusters.py

Restarts Databricks interactive clusters that were paused by
`pause_databricks_clusters.py`, reading the saved state file.

Auth: reads ~/.databrickscfg [prd] (host + token).

State file: ~/.cache/dd-chain-explorer-standby.json

Usage:
    python scripts/resume_databricks_clusters.py [--profile prd] [--dry-run]
"""

import argparse
import configparser
import json
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("ERROR: 'requests' library not found. Run: pip install requests")


# ---------------------------------------------------------------------------
# Config helpers (shared pattern with pause script)
# ---------------------------------------------------------------------------

def load_profile(profile: str) -> tuple[str, str]:
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
        sys.exit(f"ERROR: Profile [{profile}] is missing 'host' or 'token'.")

    if "accounts.cloud.databricks.com" in host:
        sys.exit(
            f"ERROR: Profile [{profile}] points to the account-level URL.\n"
            f"       Cluster operations require a workspace URL."
        )

    return host, token


def state_file_path() -> Path:
    return Path.home() / ".cache" / "dd-chain-explorer-standby.json"


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


def get_cluster_state(host: str, token: str, cluster_id: str) -> str:
    data = db_get(host, token, f"/clusters/get?cluster_id={cluster_id}")
    return data.get("state", "UNKNOWN")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Resume paused Databricks PROD interactive clusters.")
    parser.add_argument("--profile", default="prd", help="~/.databrickscfg profile (default: prd)")
    parser.add_argument("--dry-run", action="store_true", help="List saved clusters without starting")
    parser.add_argument("--no-wait", action="store_true", help="Do not wait for clusters to reach RUNNING state")
    args = parser.parse_args()

    state_path = state_file_path()

    if not state_path.exists():
        print("No standby state file found — no clusters to resume.")
        print(f"(Expected at: {state_path})")
        print("If clusters were paused manually, start them from the Databricks UI.")
        return

    state = json.loads(state_path.read_text())
    saved_clusters = state.get("clusters", [])

    if not saved_clusters:
        print("State file is empty — no clusters to resume.")
        state_path.unlink(missing_ok=True)
        return

    host, token = load_profile(args.profile)
    print(f"\n=== Databricks Cluster Resume (profile: [{args.profile}]) ===")
    print(f"Workspace: {host}\n")
    print(f"Clusters to resume ({len(saved_clusters)}):")
    for c in saved_clusters:
        print(f"  {c['cluster_id']}  {c.get('cluster_name', '<no name>')}  (paused at {c.get('paused_at', 'unknown')})")

    if args.dry_run:
        print("\n[DRY RUN] No clusters started.")
        return

    print()
    started = []
    skipped = []
    for c in saved_clusters:
        cluster_id = c["cluster_id"]
        cluster_name = c.get("cluster_name", "<no name>")

        current_state = get_cluster_state(host, token, cluster_id)
        if current_state == "RUNNING":
            print(f"  [SKIP] Already RUNNING: {cluster_name} ({cluster_id})")
            skipped.append(cluster_id)
            continue
        if current_state == "PENDING":
            print(f"  [SKIP] Already starting (PENDING): {cluster_name} ({cluster_id})")
            skipped.append(cluster_id)
            continue

        try:
            db_post(host, token, "/clusters/start", {"cluster_id": cluster_id})
            print(f"  [OK] Start requested: {cluster_name} ({cluster_id})")
            started.append(c)
        except requests.HTTPError as exc:
            print(f"  [WARN] Could not start {cluster_name} ({cluster_id}): {exc}")

    if started and not args.no_wait:
        print(f"\nWaiting for {len(started)} cluster(s) to reach RUNNING state (timeout: 10 min)...")
        deadline = time.time() + 600
        pending = {c["cluster_id"]: c.get("cluster_name", c["cluster_id"]) for c in started}
        while pending and time.time() < deadline:
            time.sleep(15)
            still_pending = {}
            for cid, cname in list(pending.items()):
                state_now = get_cluster_state(host, token, cid)
                if state_now == "RUNNING":
                    print(f"  [RUNNING] {cname} ({cid})")
                elif state_now in ("ERROR", "TERMINATED"):
                    print(f"  [FAILED]  {cname} ({cid}) — state: {state_now}")
                else:
                    still_pending[cid] = cname
            pending = still_pending

        if pending:
            print(f"\n[WARN] {len(pending)} cluster(s) did not reach RUNNING within timeout:")
            for cid, cname in pending.items():
                print(f"  {cname} ({cid})")

    state_path.unlink(missing_ok=True)
    print(f"\nState file removed: {state_path}")
    print(f"Resumed {len(started)} cluster(s), skipped {len(skipped)}.")


if __name__ == "__main__":
    main()
