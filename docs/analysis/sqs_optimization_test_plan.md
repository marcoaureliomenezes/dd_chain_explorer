# SQS Polling Optimization — Test Plan

## Pre-Test Checklist

- [ ] AWS credentials configured: `aws sts get-caller-identity`
- [ ] Databricks CLI installed: `databricks --version` (optional)
- [ ] Docker installed for local DEV testing
- [ ] Git branch: `fix/sqs-polling-optimization` or latest `develop`

## Test Scenarios

### 1. Local DEV Test (Safe — No Production Impact)

Runs both integration test scripts against your local DEV environment with reduced timeouts.

**Prerequisites:**
- DEV Databricks environment is running
- DEV Lambda/ECS functions deployed
- DEV SQS queues exist

**Steps:**

```bash
# Make sure DEV is deployed
cd dd_chain_explorer
make deploy_dev_stream    # Spin up Docker Compose streaming jobs
make dabs_deploy_dev      # Deploy DABs to DEV

# Test both scripts
bash scripts/test_integration_script.sh both

# Or test individually
bash scripts/test_integration_script.sh original
bash scripts/test_integration_script.sh optimized
```

**Expected Output:**

```
[TEST] DEV Integration Test Suite
[TEST] Validating AWS/Databricks credentials...
✅ PASS Environment validated

[TEST] ════════════════════════════════════════════════════════════════════
[TEST] Running: original
[TEST] Script: scripts/hml_integration_test.sh
[TEST] Timeout: WAIT_PHASE1_SECS=60s
[TEST] ════════════════════════════════════════════════════════════════════

[HML] Phase 0: ECS task health check
...
[HML] ✅ PASS — ECS cluster dm-chain-explorer-ecs — 5 task(s) RUNNING
...
[HML] Results: PASS=26  FAIL=0  elapsed=45s

✅ PASS original passed in 45s

[TEST] Running: optimized
...
[HML] Results: PASS=26  FAIL=0  elapsed=28s

✅ PASS optimized passed in 28s

[TEST] ════════════════════════════════════════════════════════════════════
[TEST] Comparison Results
[TEST] ════════════════════════════════════════════════════════════════════

[TEST] Original script:  45s
[TEST] Optimized script: 28s
[TEST] Reduction:       17s (38%)

✅ PASS Optimized script is faster! 🚀
```

### 2. HML Staging Test (Real Environment)

Deploy to HML and run real integration test with actual data flow.

**Prerequisites:**
- Access to GitHub Actions (can trigger workflows)
- HML Terraform infrastructure deployed
- ECR registry with RC images available

**Steps:**

1. **Manual Trigger via GitHub:**
   - Go to: https://github.com/marcoaureliomenezes/dd_chain_explorer/actions/workflows/deploy_all_dm_applications.yml
   - Click "Run workflow"
   - Select branch: `fix/sqs-polling-optimization`
   - Click "Run workflow"

2. **Monitor Output:**
   ```
   deploy_all_dm_applications
   ├── all-hml-test-streaming   ← MONITOR THIS
   │   Phase 2 (SQS):  elapsed should be <30s (vs 360s baseline)
   │   Phase 3 (Kinesis): elapsed should be <60s
   └── all-hml-test-dabs
   ```

3. **Success Criteria:**
   - [ ] Phase 2 elapsed time: <30s (target) vs 360s (baseline)
   - [ ] DLQ check completes in <10s
   - [ ] No increase in Phase 2 failures
   - [ ] Overall pipeline time: ~13 minutes faster

### 3. Regression Test

Ensure old behavior still works if we need to rollback.

**Steps:**

```bash
# Switch back to original script
git checkout develop
bash scripts/hml_integration_test.sh

# Expected: Old script still works, just slower (360s wait)
```

## Metrics to Collect

Create a file `docs/analysis/sqs_optimization_metrics.json` with results:

```json
{
  "test_date": "2026-04-24",
  "test_environment": "dev|hml",
  "test_type": "original|optimized",
  "elapsed_seconds": 45,
  "phase_2_elapsed": 10,
  "phase_3_elapsed": 28,
  "dlq_check_elapsed": 2,
  "total_retries": {
    "phase_1": 2,
    "phase_2": 1,
    "phase_3": 3
  },
  "success": true,
  "notes": "Fast-path caught SQS messages on first retry"
}
```

## DLQ Error Injection Test

Verify that DLQ detection works by intentionally injecting bad messages.

**Manual Steps:**

1. Send malformed message to test queue:
   ```bash
   aws sqs send-message \
     --queue-url "$(aws sqs get-queue-url --queue-name mainnet-mined-blocks-events-dev --query QueueUrl --output text)" \
     --message-body '{"invalid": "json' \
     --region sa-east-1
   ```

2. Run integration test:
   ```bash
   bash scripts/hml_integration_test_optimized.sh
   ```

3. Expected output:
   ```
   ❌ FAIL — SQS mainnet-mined-blocks-events-dev — DLQ has 1 rejected messages
   ```

## Timeout Tuning

If tests timeout, adjust environment variables:

```bash
# More aggressive timeout (faster fail)
export WAIT_PHASE1_SECS=60

# More lenient timeout (older behavior)
export WAIT_PHASE1_SECS=360

# Faster polling intervals
export POLL_INTERVAL=3  # default 5

bash scripts/hml_integration_test_optimized.sh
```

## Rollback Plan

If optimized script causes issues:

1. **Immediate:** Revert workflow to use old script
   ```yaml
   # .github/workflows/deploy_all_dm_applications.yml
   - if bash scripts/hml_integration_test.sh 2>&1 | tee /tmp/hml_stream_test.txt; then
   ```

2. **Restore timeout defaults:**
   ```yaml
   WAIT_PHASE1_SECS: "360"
   WAIT_KINESIS_SECS: "420"
   ```

3. **Check logs:** `docker logs dm-chain-explorer-*` for schema errors

## Success Criteria for Merge

- [ ] Local DEV test passes (both scripts)
- [ ] HML staging test shows Phase 2 <30s (vs 360s baseline)
- [ ] No new Phase 2 failures in 3 consecutive HML deploys
- [ ] DLQ error detection validated
- [ ] Backward compatibility confirmed (old script still works)
- [ ] PR approval and passing CI checks

## Post-Merge Monitoring

After merging to `develop`:

1. **Week 1:** Monitor first 5 HML deploys for Phase 2 timing
2. **Week 2:** If stable, set `WAIT_PHASE1_SECS=120` as permanent in main workflow
3. **Week 3:** Deprecate old script, add to CHANGELOG
4. **Week 4:** Remove old script from codebase (keep in git history)
