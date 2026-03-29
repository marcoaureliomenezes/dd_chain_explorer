# Agent Utilities

This directory contains scripts and state files used by Claude Code workflows.

## Structure

```
.agent-utils/
├── python/
│   ├── scan_lake_schemas.py      # Main lake schema scan script
│   └── __init__.py
├── lake_schema_state.json        # Idempotency state (auto-generated)
└── README.md                      # This file
```

## Workflows

### `/update-lake-schemas`

Scans Databricks Unity Catalog across DEV and/or PROD environments, generating a report with:
- Schema and table metadata (format, sizes, row counts, file counts)
- Data quality flags (small files, missing partitions)
- Lineage information (upstream sources, downstream consumers)
- Recommendations for optimization (OPTIMIZE, ZORDER)

**Idempotency**: Uses SHA256 fingerprints of the catalog state to skip re-scans when nothing has changed.

**Files involved**:
- `python/scan_lake_schemas.py` — scan implementation
- `lake_schema_state.json` — stores fingerprints per environment
- Output: `docs/reports/report_lake_schema.md`

See `.claude/commands/update-lake-schemas.md` for full documentation.

## Running Workflows

### Via Claude Code

```
/update-lake-schemas
```

### Via Command Line

```bash
python .agent-utils/python/scan_lake_schemas.py --environment dev
python .agent-utils/python/scan_lake_schemas.py --environment prod
python .agent-utils/python/scan_lake_schemas.py --environment both
```

Add `--force` to skip idempotency checks and re-scan even if the catalog hasn't changed.

## State Management

The `.agent-utils/lake_schema_state.json` file tracks:

```json
{
  "dev": {
    "fingerprint": "sha256:...",
    "generated_at": "2026-03-29T10:00:00Z",
    "tables_count": 18
  },
  "prod": {
    "fingerprint": "sha256:...",
    "generated_at": "2026-03-29T10:00:00Z",
    "tables_count": 25
  }
}
```

This enables idempotent workflows: scripts can check if the catalog has changed before performing expensive scans.

## Adding New Workflows

To add a new workflow:

1. Create a Python script in `.agent-utils/python/` (e.g., `my_workflow.py`)
2. Create a documentation file in `.claude/commands/` (e.g., `my-workflow.md`)
3. Update `.claude/commands/` index if needed

Follow the patterns in `scan_lake_schemas.py`:
- Use configparser to load `~/.databrickscfg` profiles
- Use requests for REST API calls
- Implement state management in `.agent-utils/`
- Document usage in the corresponding `.claude/commands/` file
