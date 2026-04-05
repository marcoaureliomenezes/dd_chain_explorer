# DABs Components — Deployment Checklist

## Pre-Deployment Verification

- [ ] All components validate: `python /tmp/validate_components.py` → 7 passed
- [ ] Databricks CLI configured: `databricks --version`
- [ ] Authenticated to DEV workspace: `databricks workspace ls`
- [ ] Permission to deploy to target workspace
- [ ] S3 buckets exist and are accessible
- [ ] Cluster/compute environment configured

---

## Phase 1: DLT Pipelines

### dlt_ethereum

- [ ] Run validation: `cd dlt_ethereum && databricks bundle validate --target dev`
- [ ] Deploy: `databricks bundle deploy --target dev`
- [ ] Verify in Databricks UI:
  - [ ] Pipeline `dm-ethereum` appears in Workflows
  - [ ] Trigger job `workflow_trigger_dlt_ethereum` appears
  - [ ] Schedule is PAUSED (expected for DEV)
- [ ] Manual test: `databricks bundle run workflow_trigger_ethereum --target dev`
  - [ ] Job starts and completes
  - [ ] Pipeline status shows success
  - [ ] Bronze tables created in `b_ethereum` schema
  - [ ] Silver tables appear in `s_apps` schema
- [ ] Document pipeline ID: `ETHEREUM_PIPELINE_ID = ________________`

### dlt_app_logs

- [ ] Run validation: `cd dlt_app_logs && databricks bundle validate --target dev`
- [ ] Deploy: `databricks bundle deploy --target dev`
- [ ] Verify in Databricks UI:
  - [ ] Pipeline `dm-app-logs` appears in Workflows
  - [ ] Trigger job `workflow_trigger_dlt_app_logs` appears
  - [ ] Schedule is PAUSED (expected for DEV)
- [ ] Manual test: `databricks bundle run workflow_trigger_app_logs --target dev`
  - [ ] Job starts and completes
  - [ ] Pipeline status shows success
  - [ ] Bronze tables created in `b_app_logs` schema
  - [ ] Silver tables appear in `s_logs` schema
- [ ] Document pipeline ID: `APPLOG_PIPELINE_ID = ________________`

---

## Phase 2: Batch Jobs (Infrastructure & Maintenance)

### job_ddl_setup

- [ ] Run validation: `cd job_ddl_setup && databricks bundle validate --target dev`
- [ ] Deploy: `databricks bundle deploy --target dev`
- [ ] Verify in Databricks UI:
  - [ ] Job `dm-ddl-setup` appears in Workflows
  - [ ] Wheel artifact `dd_chain_explorer` is built
  - [ ] Entry point `dd-setup-ddl` is registered
- [ ] Manual test: `databricks bundle run workflow_ddl_setup --target dev`
  - [ ] Job completes successfully
  - [ ] All required schemas exist:
    - [ ] `b_ethereum` (bronze)
    - [ ] `s_apps` (silver)
    - [ ] `b_app_logs` (bronze)
    - [ ] `s_logs` (silver)
    - [ ] `gold` (materialized views)
  - [ ] Table comments are set
  - [ ] Column descriptions are present

### job_delta_maintenance

- [ ] Run validation: `cd job_delta_maintenance && databricks bundle validate --target dev`
- [ ] Deploy: `databricks bundle deploy --target dev`
- [ ] Verify in Databricks UI:
  - [ ] Job `dm-dm-delta-maintenance` appears in Workflows
  - [ ] Wheel artifact `dm_delta_maintenance` is built
  - [ ] 5 entry points are registered:
    - [ ] `dm-delta-maintenance-optimize-bronze`
    - [ ] `dm-delta-maintenance-optimize-silver`
    - [ ] `dm-delta-maintenance-optimize-gold`
    - [ ] `dm-delta-maintenance-vacuum`
    - [ ] `dm-delta-maintenance-monitor`
- [ ] Manual test: `databricks bundle run workflow_dm_delta_maintenance --target dev`
  - [ ] Task 1 (optimize_bronze) completes
  - [ ] Task 2 (optimize_silver) waits for task 1, then completes
  - [ ] Task 3 (optimize_gold) waits for task 2, then completes
  - [ ] Task 4 (vacuum) waits for task 3, then completes
  - [ ] Task 5 (monitor) waits for task 4, then completes
  - [ ] All tasks show success
  - [ ] Duration is reasonable (< 10 minutes for DEV)

### job_export_gold

- [ ] Run validation: `cd job_export_gold && databricks bundle validate --target dev`
- [ ] Deploy: `databricks bundle deploy --target dev`
- [ ] Verify in Databricks UI:
  - [ ] Job `dm-dm-export-gold` appears in Workflows
  - [ ] Wheel artifact `dm_export_gold` is built
  - [ ] Entry point `dm-export-gold-export-gold` is registered
- [ ] Manual test: `databricks bundle run workflow_dm_export_gold --target dev`
  - [ ] Job completes successfully
  - [ ] S3 bucket received exported files: `s3://dm-chain-explorer-dev-ingestion/exports/`
  - [ ] CSV or Parquet files are present
  - [ ] File sizes are reasonable (not empty)

---

## Phase 3: Cross-Bundle Dependency Resolution

### Get Pipeline IDs

- [ ] Navigate to dlt_ethereum: `cd dlt_ethereum`
- [ ] Run: `databricks pipelines list --output json | jq -r '.statuses[0].pipeline_id'`
- [ ] Copy result: `ETHEREUM_PIPELINE_ID = ________________________________`
- [ ] Navigate to dlt_app_logs: `cd ../dlt_app_logs`
- [ ] Run: `databricks pipelines list --output json | jq -r '.statuses[0].pipeline_id'`
- [ ] Copy result: `APPLOG_PIPELINE_ID = ________________________________`

### Update job_trigger_all

- [ ] Open file: `job_trigger_all/databricks.yml`
- [ ] Find variables section:
  ```yaml
  variables:
    pipeline_ethereum_id:
      default: ""
    pipeline_app_logs_id:
      default: ""
  ```
- [ ] Replace with actual IDs:
  ```yaml
  variables:
    pipeline_ethereum_id:
      default: "{ETHEREUM_PIPELINE_ID}"
    pipeline_app_logs_id:
      default: "{APPLOG_PIPELINE_ID}"
  ```
- [ ] Save file
- [ ] Validate changes: `cd job_trigger_all && databricks bundle validate --target dev`
  - [ ] Should show no errors (warnings OK)

### Update job_full_refresh

- [ ] Open file: `job_full_refresh/databricks.yml`
- [ ] Find variables section and update with same IDs:
  ```yaml
  variables:
    pipeline_ethereum_id:
      default: "{ETHEREUM_PIPELINE_ID}"
    pipeline_app_logs_id:
      default: "{APPLOG_PIPELINE_ID}"
  ```
- [ ] Save file
- [ ] Validate changes: `cd job_full_refresh && databricks bundle validate --target dev`
  - [ ] Should show no errors (warnings OK)

---

## Phase 4: Orchestration Jobs

### job_trigger_all

- [ ] Run validation: `cd job_trigger_all && databricks bundle validate --target dev`
- [ ] Deploy: `databricks bundle deploy --target dev`
- [ ] Verify in Databricks UI:
  - [ ] Job `dm-trigger-all-dlts` appears in Workflows
  - [ ] Task 1: `run_dlt_ethereum` configured with pipeline_id
  - [ ] Task 2: `run_dlt_app_logs` configured with pipeline_id
  - [ ] Task 2 depends on Task 1 ✓
  - [ ] Schedule is UNPAUSED in DEV (manual trigger by default)
- [ ] Manual test: `databricks bundle run dm-trigger-all-dlts --target dev`
  - [ ] Task 1 (ethereum) starts
  - [ ] Task 1 completes successfully
  - [ ] Task 2 (app_logs) starts after Task 1 completes
  - [ ] Task 2 completes successfully
  - [ ] Both pipelines show success in workspace

### job_full_refresh

- [ ] Run validation: `cd job_full_refresh && databricks bundle validate --target dev`
- [ ] Deploy: `databricks bundle deploy --target dev`
- [ ] Verify in Databricks UI:
  - [ ] Job `dm-dlt-full-refresh` appears in Workflows
  - [ ] Task 1: `full_refresh_ethereum` configured
  - [ ] Task 2: `full_refresh_app_logs` configured (depends on Task 1)
  - [ ] Task 3: `export_gold_to_s3` configured (depends on Task 2)
  - [ ] Artifact `dm_export_gold` is resolved (path: ../job_export_gold/...)
- [ ] Manual test: `databricks bundle run workflow_dlt_full_refresh --target dev`
  - [ ] Task 1 (ethereum full refresh) completes
  - [ ] Task 2 (app_logs full refresh) starts and completes
  - [ ] Task 3 (export gold) starts and completes
  - [ ] All three tasks show success
  - [ ] S3 bucket received exported files

---

## End-to-End Data Flow Validation

- [ ] **Bronze Layer**: Tables exist and contain raw data
  - [ ] `dev.b_ethereum.*` tables populated
  - [ ] `dev.b_app_logs.*` tables populated
  - [ ] Row counts > 0 for all tables

- [ ] **Silver Layer**: Cleaned and enriched data present
  - [ ] `dev.s_apps.*` views exist and queryable
  - [ ] `dev.s_logs.*` views exist and queryable
  - [ ] Data transformations applied (dedup, type casting, enrichment)

- [ ] **Gold Layer**: Materialized views for consumption
  - [ ] `dev.gold.*` tables or views created
  - [ ] KPI metrics calculated correctly
  - [ ] Export to S3 successful

- [ ] **Job Execution**:
  - [ ] DDL setup created all required schemas
  - [ ] Delta maintenance optimized and vacuumed tables
  - [ ] Gold export wrote to S3 bucket
  - [ ] Cross-bundle orchestration worked (pipeline IDs resolved)

---

## Final Sign-Off

- [ ] All 7 components deployed successfully
- [ ] All manual tests completed with 100% success
- [ ] Data flows correctly through medallion layers
- [ ] Cross-bundle dependencies resolved
- [ ] Documentation updated and accurate
- [ ] Ready for HML deployment

---

## Sign-Off

- **Validated By**: _________________________
- **Date**: _________________________
- **Environment**: DEV
- **Status**: ☐ Ready for HML | ☐ Issues Found (see below)

### Issues Found (if any)

```
[Document any issues, blocking items, or deviations here]
```

---

## Next Steps

1. ✅ Phase 1 & 2: Deploy all components
2. ✅ Phase 3: Resolve cross-bundle dependencies
3. ✅ Phase 4: Deploy orchestration jobs
4. ⏳ Complete this checklist
5. ⏳ Deploy to HML (repeat checklist with --target hml)
6. ⏳ Deploy to PROD (repeat checklist with --target prod)
7. ⏳ Update CI/CD pipelines to use atomic components
8. ⏳ Deprecate legacy monolithic bundle (databricks.yml at apps/dabs root)

