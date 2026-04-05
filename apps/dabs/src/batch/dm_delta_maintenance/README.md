# dm-delta-maintenance

Delta Lake maintenance: optimize, vacuum, and monitor all tables

## Files generated

| File | Purpose |
|------|---------|
| `resources/workflows/workflow_dm_delta_maintenance.yml` | Databricks workflow config |
| `src/batch/dm_delta_maintenance/optimize_bronze.py` | Task implementation |
| `src/batch/dm_delta_maintenance/pyproject.toml` | Isolated wheel definition |

## Storage mode

| Environment | Compute | Table type | `--storage-mode` |
|-------------|---------|------------|-----------------|
| DEV / HML | Serverless | MANAGED | `managed` |
| PROD | Cluster | EXTERNAL (S3) | `external` |

Override in `databricks.yml` for PROD target:
```yaml
targets:
  prod:
    resources:
      jobs:
        workflow_dm_delta_maintenance:
          tasks:
            - task_key: optimize_bronze
              python_wheel_task:
                parameters:
                  - "--storage-mode"
                  - "external"
                  - "--lakehouse-bucket"
                  - ${var.ingestion_s3_bucket}
```

## Databricks bundle setup

1. Add to `databricks.yml` include:
```yaml
include:
  - resources/workflows/workflow_dm_delta_maintenance.yml
```

2. Add artifact to `databricks.yml` artifacts:
```yaml
artifacts:
  dm_delta_maintenance:
    type: whl
    path: ./src/batch/dm_delta_maintenance
```

3. Add library reference to workflow task in `workflow_dm_delta_maintenance.yml`:
```yaml
libraries:
  - whl: //dm_delta_maintenance
```
