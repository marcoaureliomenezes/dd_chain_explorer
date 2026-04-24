# Delta Lake Maintenance Job

Autonomous Databricks Asset Bundle component for Delta Lake optimization and monitoring.

## Structure

```
job_delta_maintenance/
├── databricks.yml                         # Bundle config with dev/hml/prod targets
├── resources/workflows/
│   └── workflow_dm_delta_maintenance.yml  # 5 sequential tasks
└── src/batch/dm_delta_maintenance/        # Python wheel with maintenance logic
    ├── __init__.py
    ├── optimize_bronze.py
    ├── optimize_silver.py
    ├── optimize_gold.py
    ├── vacuum.py
    ├── monitor.py
    ├── setup.py
    └── pyproject.toml
```

## Deploy

```bash
cd job_delta_maintenance

# Validate bundle
databricks bundle validate --target dev

# Deploy to target
databricks bundle deploy --target dev    # DEV
databricks bundle deploy --target hml    # HML (staging)
databricks bundle deploy --target prod   # PROD

# Run job manually
databricks bundle run workflow_dm_delta_maintenance --target dev
```

## Variables

| Variable | Default | Override |
|----------|---------|----------|
| `catalog` | `dev` | Set in `databricks.yml` target |

## Job Details

Multi-task sequential job with 5 stages:

1. **optimize_bronze** — Optimize all bronze-layer tables
2. **optimize_silver** → optimize_bronze — Optimize silver-layer tables
3. **optimize_gold** → optimize_silver — Optimize gold-layer tables
4. **vacuum** → optimize_gold — Run VACUUM RETAIN 0 HOURS
5. **monitor** → vacuum — Health check and metrics collection

**Schedule**: 4 AM and 4 PM daily (PAUSED in DEV/HML)
**Type**: `python_wheel_task`
**Artifact**: `dm_delta_maintenance` wheel

## Entry Points

Each task maps to a separate entry point in `pyproject.toml`:

```
dm-delta-maintenance-optimize-bronze = "dm_delta_maintenance.optimize_bronze:main"
dm-delta-maintenance-optimize-silver = "dm_delta_maintenance.optimize_silver:main"
dm-delta-maintenance-optimize-gold = "dm_delta_maintenance.optimize_gold:main"
dm-delta-maintenance-vacuum = "dm_delta_maintenance.vacuum:main"
dm-delta-maintenance-monitor = "dm_delta_maintenance.monitor:main"
```

Parameters passed to all tasks:
- `--catalog`: target Unity Catalog (dev/hml/dd_chain_explorer)
- `--storage-mode`: `managed`

## References

See `docs/03_data_processing.md` for data maintenance strategy.
