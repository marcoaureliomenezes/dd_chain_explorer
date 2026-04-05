# Trigger All DLT Pipelines Job

Autonomous Databricks Asset Bundle component for orchestrating DLT pipeline executions.

## Structure

```
job_trigger_all/
├── databricks.yml                    # Bundle config with dev/hml/prod targets
└── resources/workflows/
    └── workflow_trigger_dlt_all.yml  # 2 sequential pipeline tasks
```

## Deploy

```bash
cd job_trigger_all

# Validate bundle
databricks bundle validate --target dev

# Deploy to target
databricks bundle deploy --target dev    # DEV
databricks bundle deploy --target hml    # HML (staging)
databricks bundle deploy --target prod   # PROD

# Run job manually
databricks bundle run dm-trigger-all-dlts --target dev
```

## Variables (Required)

Before deploying, you must set the pipeline IDs from the deployed DLT components:

| Variable | Source | Example |
|----------|--------|---------|
| `pipeline_ethereum_id` | `databricks pipelines list` in `dlt_ethereum` workspace | `abc123def456` |
| `pipeline_app_logs_id` | `databricks pipelines list` in `dlt_app_logs` workspace | `xyz789uvw012` |

### How to Get Pipeline IDs

After deploying `dlt_ethereum` and `dlt_app_logs`:

```bash
# Get ethereum pipeline ID
cd ../dlt_ethereum
databricks pipelines list --output json | jq '.statuses[0].pipeline_id'

# Get app_logs pipeline ID
cd ../dlt_app_logs
databricks pipelines list --output json | jq '.statuses[0].pipeline_id'
```

Then update `job_trigger_all/databricks.yml` with these values:

```yaml
variables:
  pipeline_ethereum_id:
    default: "YOUR_ETHEREUM_PIPELINE_ID"
  pipeline_app_logs_id:
    default: "YOUR_APP_LOGS_PIPELINE_ID"
```

## Job Details

**Cross-Bundle References**: This job references DLT pipelines from separate components using explicit variable references (`${var.pipeline_*_id}`).

**Sequential Execution**:
1. **run_dlt_ethereum** — Start ethereum pipeline, await completion
2. **run_dlt_app_logs** → run_dlt_ethereum — Start app_logs pipeline after ethereum finishes

**Schedule**: Hourly (UNPAUSED in DEV, PAUSED in HML/PROD)

## Integration with Other Components

This component depends on:
- `dlt_ethereum` component (deployed and running)
- `dlt_app_logs` component (deployed and running)

When pipelines are re-deployed or recreated, pipeline IDs may change — update the variables accordingly.

## References

See `docs/03_data_processing.md` for pipeline orchestration strategy.
