# DABs Components — Deployment Guide

## Overview

The `apps/dabs/` directory now contains **7 atomic, independently deployable Databricks components**:

- **2 DLT Pipelines**: `dlt_ethereum`, `dlt_app_logs`
- **5 Batch Jobs**: `job_ddl_setup`, `job_delta_maintenance`, `job_export_gold`, `job_trigger_all`, `job_full_refresh`

Each component is **self-contained** with its own `databricks.yml` and can be deployed independently.

---

## Validation Status

✅ **All 7 components pass `databricks bundle validate`**

```
✓ PASS   dlt_app_logs
✓ PASS   dlt_ethereum
✓ PASS   job_ddl_setup
✓ PASS   job_delta_maintenance
✓ PASS   job_export_gold
✓ PASS   job_full_refresh
✓ PASS   job_trigger_all
```

---

## Deployment Order

### Phase 1: Deploy DLT Pipelines (Foundation)

Deploy in order. These are the data sources for everything else.

```bash
# 1. Deploy Ethereum pipeline
cd dlt_ethereum
databricks bundle validate --target dev
databricks bundle deploy --target dev
cd ..

# 2. Deploy App Logs pipeline
cd dlt_app_logs
databricks bundle validate --target dev
databricks bundle deploy --target dev
cd ..
```

**Success Criteria**:
- Both pipelines appear in Databricks workspace
- Trigger workflows are deployed and can be manually executed
- Pipelines complete successfully in DEV

---

### Phase 2: Deploy Batch Jobs (DDL & Maintenance)

These jobs don't depend on pipeline IDs yet.

```bash
# 3. Deploy DDL Setup (must run first to create schemas)
cd job_ddl_setup
databricks bundle validate --target dev
databricks bundle deploy --target dev
cd ..

# 4. Deploy Delta Maintenance
cd job_delta_maintenance
databricks bundle validate --target dev
databricks bundle deploy --target dev
cd ..

# 5. Deploy Export Gold
cd job_export_gold
databricks bundle validate --target dev
databricks bundle deploy --target dev
cd ..
```

**Success Criteria**:
- All three jobs are deployed
- Wheel artifacts build successfully
- Entry points are registered in Databricks

---

### Phase 3: Resolve Cross-Bundle Dependencies

**Components `job_trigger_all` and `job_full_refresh` require pipeline IDs** from Phase 1.

#### Step 1: Get Pipeline IDs

```bash
# Get Ethereum pipeline ID
cd dlt_ethereum
ETHEREUM_PIPELINE_ID=$(databricks pipelines list --output json | jq -r '.statuses[0].pipeline_id')
echo "Ethereum Pipeline ID: $ETHEREUM_PIPELINE_ID"

# Get App Logs pipeline ID
cd ../dlt_app_logs
APPLOG_PIPELINE_ID=$(databricks pipelines list --output json | jq -r '.statuses[0].pipeline_id')
echo "App Logs Pipeline ID: $APPLOG_PIPELINE_ID"
```

**Expected Output**:
```
Ethereum Pipeline ID: abc123def456ghi789jkl
App Logs Pipeline ID: xyz789uvw012rst345
```

#### Step 2: Update job_trigger_all

Edit `job_trigger_all/databricks.yml`:

```yaml
variables:
  pipeline_ethereum_id:
    default: "abc123def456ghi789jkl"    # ← Paste Ethereum ID here
  pipeline_app_logs_id:
    default: "xyz789uvw012rst345"       # ← Paste App Logs ID here
```

#### Step 3: Update job_full_refresh

Edit `job_full_refresh/databricks.yml` (same variable names):

```yaml
variables:
  pipeline_ethereum_id:
    default: "abc123def456ghi789jkl"    # ← Paste Ethereum ID here
  pipeline_app_logs_id:
    default: "xyz789uvw012rst345"       # ← Paste App Logs ID here
  catalog:
    default: "dev"
  ingestion_s3_bucket:
    default: "dm-chain-explorer-dev-ingestion"
```

---

### Phase 4: Deploy Orchestration Jobs

Now that pipeline IDs are resolved, deploy the orchestration jobs.

```bash
# 6. Deploy Trigger All (sequential pipeline triggering)
cd job_trigger_all
databricks bundle validate --target dev
databricks bundle deploy --target dev
cd ..

# 7. Deploy Full Refresh (pipelines + export gold)
cd job_full_refresh
databricks bundle validate --target dev
databricks bundle deploy --target dev
cd ..
```

**Success Criteria**:
- Both jobs deployed successfully
- Workflow references are valid
- Jobs can be manually triggered

---

## Testing & Validation

### Manual Testing Workflow

1. **Test DLT Pipelines**
   ```bash
   cd dlt_ethereum
   databricks bundle run workflow_trigger_ethereum --target dev
   # Monitor in Databricks UI → Workflows
   ```

2. **Test DDL Setup**
   ```bash
   cd job_ddl_setup
   databricks bundle run workflow_ddl_setup --target dev
   # Verify schemas created in Databricks Unity Catalog
   ```

3. **Test Delta Maintenance**
   ```bash
   cd job_delta_maintenance
   databricks bundle run workflow_dm_delta_maintenance --target dev
   # Verify task sequence completes: optimize_bronze → silver → gold → vacuum → monitor
   ```

4. **Test Export Gold**
   ```bash
   cd job_export_gold
   databricks bundle run workflow_dm_export_gold --target dev
   # Verify export succeeds (check S3 bucket)
   ```

5. **Test Trigger All**
   ```bash
   cd job_trigger_all
   databricks bundle run dm-trigger-all-dlts --target dev
   # Verify both pipelines execute sequentially
   ```

6. **Test Full Refresh**
   ```bash
   cd job_full_refresh
   databricks bundle run workflow_dlt_full_refresh --target dev
   # Verify 3-task sequence: ethereum refresh → app_logs refresh → export gold
   ```

### Validation Checklist

- [ ] All 7 components validate without errors
- [ ] DLT pipelines deployed and trigger workflows work
- [ ] DDL setup creates all required schemas in Unity Catalog
- [ ] Delta maintenance jobs complete successfully
- [ ] Export gold writes to S3 bucket
- [ ] job_trigger_all orchestrates sequential pipeline execution
- [ ] job_full_refresh handles full refresh + export
- [ ] Data flows correctly through medallion layers (bronze → silver → gold)
- [ ] Cross-bundle references resolved (pipeline IDs set correctly)

---

## Environment-Specific Deployment

Each component supports three targets: `dev`, `hml`, `prod`

### Development Deployment (DEV)
```bash
databricks bundle deploy --target dev
```

**Configuration**:
- Workspace: `https://dbc-409f1007-5779.cloud.databricks.com`
- Catalog: `dev`
- S3 bucket: `dm-chain-explorer-dev-ingestion`
- Pipelines: PAUSED (manual trigger only)

### Staging Deployment (HML)
```bash
databricks bundle deploy --target hml
```

**Configuration**:
- Workspace: `https://dbc-409f1007-5779.cloud.databricks.com` (same as DEV)
- Catalog: `hml`
- S3 bucket: `dm-chain-explorer-hml-lakehouse`
- Pipelines: PAUSED (trigger via CI/CD)
- Jobs: PAUSED (trigger via CI/CD)

### Production Deployment (PROD)
```bash
databricks bundle deploy --target prod
```

**Configuration**:
- Workspace: AWS workspace (empty in template — must be set)
- Catalog: `dd_chain_explorer`
- S3 bucket: `dm-chain-explorer-lakehouse`
- Pipelines: UNPAUSED (automatic schedule)
- Jobs: UNPAUSED (automatic schedule)
- Mode: `production` (requires M2M OAuth)

---

## Troubleshooting

### Error: "pipeline_id not found"

**Problem**: `job_trigger_all` or `job_full_refresh` fail because pipeline IDs are not set.

**Solution**:
1. Get pipeline IDs from Phase 3 (Step 1)
2. Update `databricks.yml` with actual IDs
3. Redeploy: `databricks bundle deploy --target dev`

### Error: "artifact not found"

**Problem**: Wheel artifact not building.

**Solution**:
1. Check `pyproject.toml` exists in job directory
2. Verify `setup.py` exists
3. Run `python -m pip install -e .` in job directory to test build
4. Redeploy

### Error: "workspace host not found"

**Problem**: Workspace URL is empty or incorrect.

**Solution**:
1. Check workspace URLs in each `databricks.yml`
2. For PROD, workspace_host_prod is intentionally empty — set before PROD deployment
3. Update and redeploy

---

## Component Dependencies

```
dlt_ethereum ──┐
               ├─→ job_trigger_all ──→ orchestrates both pipelines
dlt_app_logs ──┤
               ├─→ job_full_refresh ──→ full refresh + export

               ├─→ job_ddl_setup ──→ creates schemas (must run first)
               ├─→ job_delta_maintenance ──→ optimize + vacuum (runs post-pipeline)
               └─→ job_export_gold ──→ export gold tables (runs post-pipeline)
```

---

## File Structure

```
apps/dabs/
├── DEPLOYMENT_GUIDE.md                  # ← This file
├── databricks.yml                       # Legacy bundle (keep for backward compatibility)
├── resources/                           # Legacy resources (will eventually deprecate)
├── src/                                 # Legacy source code
├── dlt_ethereum/
│   ├── databricks.yml
│   ├── resources/dlt/pipeline_ethereum.yml
│   ├── resources/workflows/workflow_trigger_dlt_ethereum.yml
│   ├── src/streaming/ethereum_pipeline.py
│   └── README.md
├── dlt_app_logs/
│   ├── databricks.yml
│   ├── resources/dlt/pipeline_app_logs.yml
│   ├── resources/workflows/workflow_trigger_dlt_app_logs.yml
│   ├── src/streaming/app_logs_pipeline.py
│   └── README.md
├── job_ddl_setup/
│   ├── databricks.yml
│   ├── resources/workflows/workflow_ddl_setup.yml
│   ├── src/dd_chain_explorer/
│   └── README.md
├── job_delta_maintenance/
│   ├── databricks.yml
│   ├── resources/workflows/workflow_dm_delta_maintenance.yml
│   ├── src/batch/dm_delta_maintenance/
│   └── README.md
├── job_export_gold/
│   ├── databricks.yml
│   ├── resources/workflows/workflow_dm_export_gold.yml
│   ├── src/batch/dm_export_gold/
│   └── README.md
├── job_trigger_all/
│   ├── databricks.yml                   # ← Must add pipeline IDs here
│   ├── resources/workflows/workflow_trigger_dlt_all.yml
│   └── README.md
└── job_full_refresh/
    ├── databricks.yml                   # ← Must add pipeline IDs here
    ├── resources/workflows/workflow_dlt_full_refresh.yml
    └── README.md
```

---

## Next Steps

1. ✅ Validate all components (DONE)
2. ⏳ Deploy Phase 1 (DLT pipelines)
3. ⏳ Deploy Phase 2 (Batch jobs)
4. ⏳ Resolve cross-bundle dependencies (get pipeline IDs, update YAML)
5. ⏳ Deploy Phase 3 (Orchestration jobs)
6. ⏳ Manual testing & validation
7. ⏳ Update CI/CD to deploy atomic components
8. ⏳ Deprecate legacy monolithic bundle

---

## References

- [Databricks Asset Bundles](https://docs.databricks.com/en/dev-tools/bundles/)
- [beteugeuse ROADMAP](../../beteugeuse/ROADMAP.md) — Scaffolding library roadmap
- [dd_chain_explorer DABs README](./README.md) — Component overview

---

**Last Updated**: 2024-04-04
**Status**: All components validated ✅
**Next Phase**: Manual testing in DEV environment
