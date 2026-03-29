#!/usr/bin/env python3
"""
USAGE: python3 .agent-utils/python/scan_lake_schemas.py --environment dev|prod|both [--force]


.agent-utils/python/scan_lake_schemas.py

Scans Databricks Unity Catalog for schema/table metadata, lineage, and quality metrics.
Generates a report and maintains idempotency via fingerprinting.

Usage:
    python .agent-utils/python/scan_lake_schemas.py \\
        --environment dev|prod|both \\
        [--force] [--profile-dev <name>] [--profile-prod <name>] \\
        [--warehouse-id <id>] [--output <path>]
"""

import argparse
import configparser
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    sys.exit("ERROR: 'requests' library not found. Run: pip install requests")


# ============================================================================
# Config & State Management
# ============================================================================

REPO_ROOT = Path(__file__).parent.parent.parent
STATE_FILE = REPO_ROOT / ".agent-utils" / "lake_schema_state.json"
DEFAULT_REPORT_PATH = REPO_ROOT / "docs" / "reports" / "report_lake_schema.md"

CATALOG_MAP = {
    "dev": "dev",
    "prod": "dd_chain_explorer",
}

WORKSPACE_MAP = {
    "dev": "https://dbc-409f1007-5779.cloud.databricks.com",
}


def load_profile(profile: str) -> tuple[str, str]:
    """Load host and token from ~/.databrickscfg for given profile."""
    cfg_path = Path.home() / ".databrickscfg"
    if not cfg_path.exists():
        sys.exit(f"ERROR: ~/.databrickscfg not found. Run: databricks configure --profile {profile}")

    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)

    # Special case: profile "DEFAULT" uses configparser's DEFAULT section
    if profile == "DEFAULT":
        host = cfg.defaults().get("host", "").rstrip("/")
        token = cfg.defaults().get("token", "")
    # Try exact match in named sections
    elif profile in cfg.sections():
        host = cfg[profile].get("host", "").rstrip("/")
        token = cfg[profile].get("token", "")
    # Fall back to DEFAULT for dev profile if not found
    elif profile == "dev":
        host = cfg.defaults().get("host", "").rstrip("/")
        token = cfg.defaults().get("token", "")
    else:
        all_sections = list(cfg.sections())
        if cfg.defaults():
            all_sections.append("DEFAULT")
        sys.exit(
            f"ERROR: Profile [{profile}] not found in ~/.databrickscfg.\n"
            f"       Available: {all_sections}"
        )

    if not host or not token:
        sys.exit(f"ERROR: Profile [{profile}] missing 'host' or 'token'.")

    if "accounts.cloud.databricks.com" in host:
        sys.exit(f"ERROR: Profile [{profile}] points to account URL. Use workspace URL.")

    # Strip query parameters from workspace URL
    if "?" in host:
        host = host.split("?")[0]

    return host, token


def load_state() -> dict:
    """Load idempotency state file."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_state(state: dict) -> None:
    """Save idempotency state file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ============================================================================
# REST API Helpers
# ============================================================================

def db_get(host: str, token: str, path: str, params: Optional[dict] = None) -> dict:
    """Databricks REST GET request."""
    try:
        resp = requests.get(
            f"{host}/api/2.1{path}" if path.startswith("/unity-catalog") else f"{host}/api/2.0{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params or {},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        print(f"  [ERROR] GET {path}: {e.response.status_code} {e.response.text[:200]}")
        return {}
    except Exception as e:
        print(f"  [ERROR] GET {path}: {e}")
        return {}


def db_post(host: str, token: str, path: str, payload: dict) -> dict:
    """Databricks REST POST request."""
    try:
        resp = requests.post(
            f"{host}/api/2.0{path}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        print(f"  [ERROR] POST {path}: {e.response.status_code} {e.response.text[:200]}")
        return {}
    except Exception as e:
        print(f"  [ERROR] POST {path}: {e}")
        return {}


# ============================================================================
# Fingerprinting (Fast Idempotency Check)
# ============================================================================

def compute_fingerprint(host: str, token: str, catalog: str) -> str:
    """
    Fast fingerprint: SHA256 of sorted schema+table list + updated_at timestamps.
    If listing fails, return empty string (graceful degradation).
    """
    # Fetch all schemas first
    result = db_get(host, token, "/unity-catalog/schemas", {"catalog_name": catalog})
    schemas = result.get("objects", [])

    if not schemas:
        return ""

    # Collect all tables across schemas
    all_tables = []
    for schema in schemas:
        schema_name = schema.get("name", "")
        result = db_get(host, token, "/unity-catalog/tables", {
            "catalog_name": catalog,
            "schema_name": schema_name,
        })
        tables = result.get("objects", [])
        all_tables.extend(tables)

    if not all_tables:
        return ""

    # Sort by full_name and extract fingerprint seed
    tables_sorted = sorted(all_tables, key=lambda t: t.get("full_name", ""))
    seed_parts = [f"{t.get('full_name')}|{t.get('updated_at', 0)}" for t in tables_sorted]
    seed = "\n".join(seed_parts)

    return hashlib.sha256(seed.encode()).hexdigest()


# ============================================================================
# Catalog Scan
# ============================================================================

def discover_warehouse(host: str, token: str) -> Optional[str]:
    """Auto-discover first running SQL warehouse."""
    result = db_get(host, token, "/sql/warehouses")
    warehouses = result.get("objects", [])

    for wh in warehouses:
        if wh.get("state") == "RUNNING":
            return wh.get("id")

    # Return first one (may be stopped)
    if warehouses:
        return warehouses[0].get("id")

    return None


def execute_sql(host: str, token: str, warehouse_id: str, sql: str, timeout_sec: int = 60) -> list[dict]:
    """Execute SQL and return result rows."""
    if not warehouse_id:
        print(f"  [WARN] No warehouse ID provided, skipping SQL query")
        return []

    payload = {
        "warehouse_id": warehouse_id,
        "statement": sql,
        "wait_timeout": f"{timeout_sec}s",
    }

    result = db_post(host, token, "/sql/statements", payload)

    if "result" not in result:
        return []

    rows = result.get("result", {}).get("data_rows", [])
    return rows or []


def get_table_detail(
    host: str,
    token: str,
    warehouse_id: str,
    catalog: str,
    schema: str,
    table: str,
) -> dict:
    """Fetch DESCRIBE DETAIL info for a table."""
    fqn = f"{catalog}.{schema}.{table}"

    # DESCRIBE DETAIL returns numFiles, sizeInBytes, etc.
    sql = f"DESCRIBE DETAIL {fqn}"
    rows = execute_sql(host, token, warehouse_id, sql, timeout_sec=30)

    detail = {}
    if rows:
        row = rows[0]
        # Row format: [format, id, name, description, location, createdAt, lastModified,
        #              partitionColumns, numFiles, sizeInBytes, properties]
        if len(row) >= 9:
            detail = {
                "format": row[0] or "UNKNOWN",
                "location": row[4] or "",
                "created_at": row[5] or "",
                "last_modified": row[6] or "",
                "partition_columns": json.loads(row[7]) if row[7] and row[7] != "[]" else [],
                "num_files": row[8] or 0,
                "size_bytes": row[9] or 0,
            }

    return detail


def get_table_row_count(
    host: str,
    token: str,
    warehouse_id: str,
    catalog: str,
    schema: str,
    table: str,
) -> int:
    """Quick row count estimate."""
    fqn = f"{catalog}.{schema}.{table}"
    sql = f"SELECT COUNT(*) as cnt FROM {fqn}"

    rows = execute_sql(host, token, warehouse_id, sql, timeout_sec=60)
    if rows and len(rows[0]) > 0:
        try:
            return int(rows[0][0])
        except (ValueError, TypeError):
            return 0

    return 0


def get_lineage(host: str, token: str, catalog: str, schema: str, table: str) -> dict:
    """Fetch lineage via lineage tracking API. Gracefully degrade if not available."""
    fqn = f"{catalog}.{schema}.{table}"

    result = db_get(host, token, "/lineage-tracking/table-lineage", {"table_name": fqn})

    upstreams = []
    downstreams = []

    if "upstreams" in result:
        for up in result.get("upstreams", []):
            upstreams.append(up.get("table_name", up.get("external_location", "")))

    if "downstreams" in result:
        for down in result.get("downstreams", []):
            downstreams.append(down.get("table_name", down.get("external_location", "")))

    return {
        "upstreams": upstreams,
        "downstreams": downstreams,
    }


def scan_catalog(
    host: str,
    token: str,
    warehouse_id: Optional[str],
    catalog: str,
    environment: str,
) -> dict:
    """Full catalog scan: schemas, tables, lineage, quality metrics."""
    print(f"\n  Scanning catalog '{catalog}' in {environment}...")

    result = db_get(host, token, "/unity-catalog/schemas", {"catalog_name": catalog})
    schemas = result.get("objects", [])

    print(f"  Found {len(schemas)} schema(s)")

    # Compute fingerprint for idempotency
    fingerprint = compute_fingerprint(host, token, catalog)

    catalog_data = {
        "environment": environment,
        "catalog": catalog,
        "scanned_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "fingerprint": fingerprint,
        "schemas": [],
    }

    total_size_bytes = 0
    total_files = 0
    total_rows = 0
    total_tables = 0
    small_files_tables = []

    for schema_obj in schemas:
        schema_name = schema_obj.get("name", "")
        print(f"    Schema: {schema_name}...", end=" ", flush=True)

        result = db_get(host, token, "/unity-catalog/tables", {
            "catalog_name": catalog,
            "schema_name": schema_name,
        })
        tables = result.get("objects", [])
        print(f"{len(tables)} tables")

        schema_data = {
            "name": schema_name,
            "tables": [],
        }

        for table_obj in tables:
            table_name = table_obj.get("name", "")
            total_tables += 1

            # Fetch detailed metadata
            detail = get_table_detail(host, token, warehouse_id or "", catalog, schema_name, table_name)
            row_count = 0

            if warehouse_id:
                row_count = get_table_row_count(host, token, warehouse_id, catalog, schema_name, table_name)

            size_bytes = detail.get("size_bytes", 0) or 0
            num_files = detail.get("num_files", 0) or 0
            total_size_bytes += size_bytes
            total_files += num_files
            total_rows += row_count

            # Compute avg file size
            avg_file_size_mb = (size_bytes / (1024 * 1024)) / max(num_files, 1) if num_files > 0 else 0

            # Flag small files issue
            has_small_files = False
            if avg_file_size_mb < 128 and num_files > 10:
                has_small_files = True
                small_files_tables.append(f"{catalog}.{schema_name}.{table_name}")

            # Fetch lineage
            lineage = get_lineage(host, token, catalog, schema_name, table_name)

            # Format dates
            created_at_str = detail.get("created_at", "").split("T")[0] if detail.get("created_at") else ""
            last_modified_str = detail.get("last_modified", "").split("T")[0] if detail.get("last_modified") else ""

            table_data = {
                "name": table_name,
                "format": detail.get("format", "UNKNOWN"),
                "location": detail.get("location", ""),
                "row_count": row_count,
                "size_bytes": size_bytes,
                "size_mb": round(size_bytes / (1024 * 1024), 2),
                "num_files": num_files,
                "avg_file_size_mb": round(avg_file_size_mb, 2),
                "has_small_files": has_small_files,
                "partition_columns": detail.get("partition_columns", []),
                "is_partitioned": len(detail.get("partition_columns", [])) > 0,
                "created_at": created_at_str,
                "last_modified": last_modified_str,
                "lineage_upstreams": lineage.get("upstreams", []),
                "lineage_downstreams": lineage.get("downstreams", []),
            }

            schema_data["tables"].append(table_data)

        catalog_data["schemas"].append(schema_data)

    # Summary stats
    catalog_data["summary"] = {
        "total_schemas": len(schemas),
        "total_tables": total_tables,
        "total_size_bytes": total_size_bytes,
        "total_size_gb": round(total_size_bytes / (1024 ** 3), 2),
        "total_files": total_files,
        "total_rows": total_rows,
        "small_files_issues": len(small_files_tables),
        "small_files_tables": small_files_tables,
    }

    return catalog_data


# ============================================================================
# Report Generation
# ============================================================================

def format_bytes(b: int) -> str:
    """Format bytes to human-readable."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def generate_report_section(scan_data: dict) -> str:
    """Generate markdown section for one environment."""
    env = scan_data["environment"]
    catalog = scan_data["catalog"]
    scanned_at = scan_data["scanned_at"].split("T")[0]
    summary = scan_data["summary"]

    lines = []
    lines.append(f"## {env.upper()} (Catalog: `{catalog}`)")
    lines.append("")
    lines.append("### Visão Geral")
    lines.append("")
    lines.append("| Métrica | Valor |")
    lines.append("|---------|-------|")
    lines.append(f"| Total de Schemas | {summary['total_schemas']} |")
    lines.append(f"| Total de Tabelas | {summary['total_tables']} |")
    lines.append(f"| Tamanho Total Estimado | {summary['total_size_gb']} GB |")
    lines.append(f"| Total de Arquivos | {summary['total_files']:,} |")
    lines.append(f"| Total de Linhas | {summary['total_rows']:,} |")
    lines.append(f"| Última Atualização | {scanned_at} |")
    lines.append("")

    lines.append("### Schemas e Tabelas")
    lines.append("")

    for schema in scan_data["schemas"]:
        schema_name = schema["name"]
        lines.append(f"#### Schema: `{schema_name}`")
        lines.append("")
        lines.append("| Tabela | Formato | Linhas | Tamanho | Arquivos | Particionada | Small Files | Última Mod. |")
        lines.append("|--------|---------|--------|---------|----------|-------------|-------------|-------------|")

        for table in schema["tables"]:
            name = table["name"]
            fmt = table["format"]
            rows = f"{table['row_count']:,}" if table["row_count"] else "N/A"
            size = f"{table['size_mb']} MB" if table["size_mb"] > 0 else "-"
            files = table["num_files"]
            partitioned = "✅ Sim" if table["is_partitioned"] else "Não"
            small_files = "⚠️ SIM" if table["has_small_files"] else "✅ OK"
            last_mod = table.get("last_modified", "-")

            lines.append(f"| {name} | {fmt} | {rows} | {size} | {files} | {partitioned} | {small_files} | {last_mod} |")

        lines.append("")

        # Lineage summary
        for table in schema["tables"]:
            if table["lineage_upstreams"] or table["lineage_downstreams"]:
                lines.append(f"**Lineage: {table['name']}**")
                if table["lineage_upstreams"]:
                    lines.append(f"  - Upstream: {', '.join(table['lineage_upstreams'])}")
                if table["lineage_downstreams"]:
                    lines.append(f"  - Downstream: {', '.join(table['lineage_downstreams'])}")
                lines.append("")

    # Quality analysis
    if summary["small_files_issues"] > 0:
        lines.append("### Análise de Qualidade")
        lines.append("")
        lines.append("| Problema | Tabelas Afetadas | Recomendação |")
        lines.append("|----------|-----------------|--------------|")
        lines.append(f"| Small files (< 128 MB avg) | {summary['small_files_issues']} | OPTIMIZE + ZORDER |")
        lines.append("")

        for table in summary["small_files_tables"]:
            lines.append(f"  - `{table}`")
        lines.append("")

    # How to use
    lines.append("### Como Usar esses Dados (Serving Layer)")
    lines.append("")
    lines.append("Tabelas Silver (prefixo `s_`) e Gold (prefixo `g_` ou schemas `gold*`) estão otimizadas para:")
    lines.append("- **Dashboards Lakeview**: tabelas com prefixo `s_` e `g_` são candidatas")
    lines.append("- **Genie Spaces**: use tabelas Gold com agregações e dimensões claras")
    lines.append("- **Power BI / BI Tools**: exporte via Gold layer via S3 (veja `04_export_gold_to_s3.py`)")
    lines.append("")

    return "\n".join(lines)


def update_report(report_path: Path, scan_data: dict) -> None:
    """Update or create report, replacing environment section."""
    environment = scan_data["environment"]
    section_header = f"## {environment.upper()}"

    # Read existing
    if report_path.exists():
        content = report_path.read_text()
    else:
        # Create header
        content = "# Lake Schema Report\n\n"

    # Metadata
    fingerprint = scan_data.get("fingerprint", "")[:16] + "..." if scan_data.get("fingerprint") else "N/A"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    metadata_line = f"> **{environment.upper()} atualizado em:** {scan_data['scanned_at'][:10]} | "
    metadata_line += f"**{environment.upper()} fingerprint:** `{fingerprint[:16]}...` | "
    metadata_line += f"**Gerado por:** `/update-lake-schemas`"

    lines = content.split("\n")

    # Find or add metadata section
    metadata_found = False
    for i, line in enumerate(lines):
        if f"**{environment.upper()} atualizado em:**" in line:
            lines[i] = metadata_line
            metadata_found = True
            break

    if not metadata_found:
        # Insert after title
        insert_pos = 1
        if len(lines) > 1 and lines[1].startswith(">"):
            insert_pos = 2

        lines.insert(insert_pos, metadata_line)

    # Remove existing section for this environment
    new_lines = []
    skip_section = False
    for line in lines:
        if line.startswith(section_header):
            skip_section = True
            continue
        elif skip_section and line.startswith("## "):
            skip_section = False

        if not skip_section:
            new_lines.append(line)

    # Append new section
    new_lines.append("")
    new_lines.append(generate_report_section(scan_data))
    new_lines.append("")

    report_path.write_text("\n".join(new_lines))


# ============================================================================
# Main
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Scan Databricks catalog and generate lake schema report")
    parser.add_argument("--environment", required=True, choices=["dev", "prod", "both"],
                        help="Environment to scan")
    parser.add_argument("--force", action="store_true", help="Skip idempotency check")
    parser.add_argument("--profile-dev", default="dev", help="Profile for DEV (default: dev)")
    parser.add_argument("--profile-prod", default="prd", help="Profile for PROD (default: prd)")
    parser.add_argument("--warehouse-id", default="", help="Warehouse ID for SQL execution")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT_PATH, help="Report output path")

    args = parser.parse_args()

    state = load_state()
    envs_to_scan = ["dev", "prod"] if args.environment == "both" else [args.environment]
    all_scan_data = []

    for env in envs_to_scan:
        catalog = CATALOG_MAP.get(env, "")
        if env == "dev":
            host, token = load_profile(args.profile_dev)
        else:
            host, token = load_profile(args.profile_prod)

        print(f"\n=== Scanning {env.upper()} ===")
        print(f"Workspace: {host}")
        print(f"Catalog: {catalog}")

        # Fingerprint check
        current_fp = compute_fingerprint(host, token, catalog)
        state_fp = state.get(env, {}).get("fingerprint", "")

        if current_fp and state_fp and current_fp == state_fp and not args.force:
            print(f"✅ No changes detected since last scan (fingerprint unchanged)")
            continue

        if not current_fp:
            if state_fp:
                print("⚠️ Could not compute fingerprint (catalog API may be unavailable), skipping idempotency check")
            else:
                print("⚠️ Could not compute fingerprint (catalog might be empty or not available)")

        # Auto-discover warehouse if not provided
        warehouse_id = args.warehouse_id
        if not warehouse_id:
            warehouse_id = discover_warehouse(host, token)
            if warehouse_id:
                print(f"Auto-discovered warehouse: {warehouse_id}")

        # Full scan
        scan_data = scan_catalog(host, token, warehouse_id, catalog, env)

        # Update report
        update_report(args.output, scan_data)
        print(f"✅ Report updated: {args.output}")

        # Update state (use fingerprint from scan_data if available)
        state[env] = {
            "fingerprint": scan_data.get("fingerprint", ""),
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "tables_count": scan_data["summary"]["total_tables"],
        }

        all_scan_data.append(scan_data)

    # Save state
    save_state(state)
    print(f"\n✅ State saved: {STATE_FILE}")

    # Summary
    if all_scan_data:
        print("\n=== Summary ===")
        for scan in all_scan_data:
            s = scan["summary"]
            print(f"{scan['environment'].upper()}: {s['total_schemas']} schemas, "
                  f"{s['total_tables']} tables, {s['total_size_gb']} GB, "
                  f"{s['small_files_issues']} small-files issues")


if __name__ == "__main__":
    main()
