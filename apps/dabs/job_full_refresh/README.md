# Full Refresh Job

Autonomous Databricks Asset Bundle component for full reprocessing of DLT pipelines and gold data export.

## Structure

```
job_full_refresh/
├── databricks.yml                        # Bundle config with dev/hml/prod targets + artifact reference
└── resources/workflows/
    └── workflow_dlt_full_refresh.yml     # 3 sequential tasks: 2 pipeline refreshes + 1 export
```

## Deploy

```bash
cd job_full_refresh

# Validate bundle
databricks bundle validate --target dev

# Deploy to target
databricks bundle deploy --target dev    # DEV
databricks bundle deploy --target hml    # HML (staging)
databricks bundle deploy --target prod   # PROD

# Run job manually
databricks bundle run workflow_dlt_full_refresh --target dev
```

## Variables (Required)

Before deploying, you must set the pipeline IDs from the deployed DLT components:

| Variable | Source | Example |
|----------|--------|---------|
| `catalog` | Inherited from target | `dev`, `hml`, or `dd_chain_explorer` |
| `ingestion_s3_bucket` | Inherited from target | Target-specific S3 bucket |
| `pipeline_ethereum_id` | `databricks pipelines list` in `dlt_ethereum` workspace | `abc123def456` |
| `pipeline_app_logs_id` | `databricks pipelines list` in `dlt_app_logs` workspace | `xyz789uvw012` |

### How to Get and Set Pipeline IDs

After deploying `dlt_ethereum` and `dlt_app_logs`:

```bash
# Get ethereum pipeline ID
cd ../dlt_ethereum
ETHEREUM_ID=$(databricks pipelines list --output json | jq -r '.statuses[0].pipeline_id')

# Get app_logs pipeline ID
cd ../dlt_app_logs
APPLOG_ID=$(databricks pipelines list --output json | jq -r '.statuses[0].pipeline_id')

# Update job_full_refresh databricks.yml
cd ../job_full_refresh
sed -i "s|default: \"\".*# ethereum|default: \"$ETHEREUM_ID\"  # ethereum|" databricks.yml
sed -i "s|default: \"\".*# app_logs|default: \"$APPLOG_ID\"  # app_logs|" databricks.yml
```

## Job Details

**Three-Stage Sequential Execution**:

1. **full_refresh_ethereum** — Full refresh of ethereum DLT pipeline (discards checkpoints, reprocesses all data)
2. **full_refresh_app_logs** → full_refresh_ethereum — Full refresh of app_logs DLT pipeline
3. **export_gold_to_s3** → full_refresh_app_logs — Export gold tables to S3 for external consumption

**Artifact Reference**: Uses relative path to `job_export_gold` component for the `dm_export_gold` wheel:
```yaml
artifacts:
  dm_export_gold:
    type: whl
    path: ../job_export_gold/src/batch/dm_export_gold
```

**Type**: Manual trigger only (no schedule)

## Integration with Other Components

This component depends on:
- `dlt_ethereum` component (deployed and running)
- `dlt_app_logs` component (deployed and running)
- `job_export_gold` component (for its wheel artifact)

## Use Cases

- **Backfill**: Reprocess historical data after schema changes or bug fixes
- **Recovery**: Re-sync data after a failed pipeline run
- **Testing**: Full test cycle in DEV/HML before production release

## References

See `docs/03_data_processing.md` for pipeline reprocessing strategy.
