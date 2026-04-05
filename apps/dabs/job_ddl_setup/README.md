# DDL Setup Job

Autonomous Databricks Asset Bundle component for database schema initialization.

## Structure

```
job_ddl_setup/
├── databricks.yml                      # Bundle config with dev/hml/prod targets
├── resources/workflows/
│   └── workflow_ddl_setup.yml          # Single task: setup_ddl
└── src/dd_chain_explorer/              # Python wheel with DDL logic
    ├── ddl/
    │   └── setup_ddl.py
    └── pyproject.toml
```

## Deploy

```bash
cd job_ddl_setup

# Validate bundle
databricks bundle validate --target dev

# Deploy to target
databricks bundle deploy --target dev    # DEV
databricks bundle deploy --target hml    # HML (staging)
databricks bundle deploy --target prod   # PROD

# Run job manually
databricks bundle run workflow_ddl_setup --target dev
```

## Variables

| Variable | Default | Override |
|----------|---------|----------|
| `catalog` | `dev` | Set in `databricks.yml` target |
| `ingestion_s3_bucket` | `dm-chain-explorer-dev-ingestion` | Per-target |

## Job Details

- **Single task**: `setup_ddl` — creates schemas and tables with proper comments
- **Artifact**: `dd_chain_explorer` wheel (shared across all batch jobs)
- **Entry point**: `dd-setup-ddl` (maps to `dd_chain_explorer.ddl.setup_ddl:main`)
- **Type**: `python_wheel_task`

## Entry Point

The job runs the entry point defined in `src/dd_chain_explorer/pyproject.toml`:

```
dd-setup-ddl = "dd_chain_explorer.ddl.setup_ddl:main"
```

Parameters passed to the task:
- `--catalog`: target Unity Catalog (dev/hml/dd_chain_explorer)
- `--lakehouse-s3-bucket`: S3 bucket for external table locations

## References

See `docs/03_data_processing.md` for DDL schema definitions.
