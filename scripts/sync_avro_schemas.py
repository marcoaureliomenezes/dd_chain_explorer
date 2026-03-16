#!/usr/bin/env python3
"""
Sync Avro schemas to a Confluent Schema Registry instance.

Reads every schema JSON file from the canonical source directory
(docker/onchain-stream-txs/src/schemas/) and registers each one
on the target Schema Registry, enforcing BACKWARD compatibility.

Idempotent: safe to run multiple times; already-registered schemas
that have not changed are left untouched.

Usage
-----
    # DEV (local Schema Registry)
    python scripts/sync_avro_schemas.py --sr-url http://localhost:8081

    # PROD (ECS Schema Registry via SSH tunnel or VPN)
    python scripts/sync_avro_schemas.py --sr-url http://<sr-host>:8081

    # Dry-run (print what would be registered, do nothing)
    python scripts/sync_avro_schemas.py --sr-url http://localhost:8081 --dry-run

Requirements: requests  (pip install requests)
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Canonical mapping: subject → relative path (from this repo root)
# Must match the schema_name / schema_path used in the Python streaming apps.
# ---------------------------------------------------------------------------
SCHEMAS_DIR = Path(__file__).parent.parent / "docker" / "onchain-stream-txs" / "src" / "schemas"

SCHEMA_MAP = [
    ("application-logs-schema",       SCHEMAS_DIR / "0_application_logs_avro.json"),
    ("mined-block-event-schema",      SCHEMAS_DIR / "1_mined_block_event_schema_avro.json"),
    ("block-data-schema",             SCHEMAS_DIR / "2_block_data_schema_avro.json"),
    ("transaction-hash-ids-schema",   SCHEMAS_DIR / "3_transaction_hash_ids_schema_avro.json"),
    ("transactions-schema",           SCHEMAS_DIR / "4_transactions_schema_avro.json"),
    ("input-transaction-schema",      SCHEMAS_DIR / "txs_contract_call_decoded.json"),
]

COMPATIBILITY_MODE = "BACKWARD"


def _set_compatibility(sr_url: str, subject: str, mode: str, dry_run: bool) -> None:
    if dry_run:
        print(f"  [DRY-RUN] PUT /config/{subject} -> {{compatibility: {mode}}}")
        return
    url = f"{sr_url}/config/{subject}"
    r = requests.put(url, json={"compatibility": mode}, timeout=10)
    r.raise_for_status()
    print(f"  Compatibility set to {mode}.")


def _register_schema(sr_url: str, subject: str, schema_path: Path, dry_run: bool) -> None:
    schema_json_str = schema_path.read_text()
    # Validate it's parseable JSON (catches file corruption early)
    json.loads(schema_json_str)

    check_url = f"{sr_url}/subjects/{subject}/versions/latest"
    r = requests.get(check_url, timeout=10)

    if r.status_code == 200:
        print(f"  Already registered (id={r.json().get('id', '?')}).")
    elif r.status_code == 404:
        if dry_run:
            print(f"  [DRY-RUN] POST /subjects/{subject}/versions")
        else:
            payload = {"schema": schema_json_str, "schemaType": "AVRO"}
            reg_url = f"{sr_url}/subjects/{subject}/versions"
            resp = requests.post(reg_url, json=payload, timeout=10)
            resp.raise_for_status()
            print(f"  Registered (id={resp.json()['id']}).")
    else:
        r.raise_for_status()

    _set_compatibility(sr_url, subject, COMPATIBILITY_MODE, dry_run)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Avro schemas to Confluent Schema Registry")
    parser.add_argument("--sr-url", required=True, help="Schema Registry base URL (e.g. http://localhost:8081)")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without making any changes")
    args = parser.parse_args()

    sr_url = args.sr_url.rstrip("/")

    # Validate SR connectivity
    try:
        health = requests.get(f"{sr_url}/subjects", timeout=10)
        health.raise_for_status()
    except Exception as exc:
        print(f"ERROR: Cannot reach Schema Registry at {sr_url}: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Schema Registry: {sr_url}")
    print(f"Dry-run:         {args.dry_run}")
    print(f"Schemas dir:     {SCHEMAS_DIR}\n")

    errors = []
    for subject, schema_path in SCHEMA_MAP:
        print(f"[{subject}]")
        if not schema_path.exists():
            msg = f"  ERROR: file not found: {schema_path}"
            print(msg)
            errors.append(msg)
            continue
        try:
            _register_schema(sr_url, subject, schema_path, args.dry_run)
        except Exception as exc:
            msg = f"  ERROR: {exc}"
            print(msg)
            errors.append(msg)

    print()
    if errors:
        print(f"Finished with {len(errors)} error(s):")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        print("All schemas synced successfully.")


if __name__ == "__main__":
    main()
