# SQS Polling Optimization — HML Integration Test

**Issue:** Phase 2 (SQS validation) in HML pipeline waits **360+ seconds** even when data arrives in seconds, blocking the pipeline and increasing CI time by ~13+ minutes per deploy.

**Root Cause:** The integration test relies on CloudWatch metrics which have up to 5-15 minutes of lag. The script waits for this metric to update before passing, even though the SQS queue has data immediately available.

## Optimizations Implemented

### Optimization A: Faster Fast-Path Polling
**Before:** `POLL_INTERVAL=15` seconds
**After:** `POLL_INTERVAL=5` seconds

- Reduces response time for SQS fast-path from 15-30s to 5-10s
- Catches messages in queue immediately after ECS containers start writing
- Minimal AWS API cost (SQS GetQueueAttributes is free tier)

### Optimization B: SQS ReceiveMessage Validation
**New:** Validate that messages are actually consumable, not just present

```bash
# Fast path 2: SQS ReceiveMessage
sqs_receive_message "$SQS_URL"  # Proves queue is not locked, messages are valid
```

Benefits:
- Catches schema/format errors early (malformed messages in DLQ)
- Proves queue is accessible and not in weird state
- Fails fast if messages are consistently rejected

### Optimization C: DLQ Checks
**New:** Check Dead Letter Queue before waiting

```bash
# If DLQ has messages, fail immediately
DLQ_URL=$(sqs_dlq_check "$QUEUE")
if [ -n "$DLQ_URL" ]; then
  DLQ_MSGS=$(sqs_dlq_messages "$DLQ_URL")
  if [ "${DLQ_MSGS:-0}" -gt 0 ]; then
    fail "SQS ${QUEUE} — DLQ has ${DLQ_MSGS} rejected messages"
  fi
fi
```

Benefits:
- Identifies schema/validation issues immediately (not after 6 minutes)
- Saves time on message format bugs in ECS containers
- Provides clear actionable error message

### Optimization D: Improved Logging
**New:** Retry counters, time estimates, phase timing

```bash
log "   → retry #${RETRY_COUNT} — not yet, waiting ${POLL_INTERVAL}s (${REMAINING}s remaining) ..."
```

Benefits:
- See progress (how many retries, time left)
- Understand why test is waiting
- Diagnose slowness patterns (e.g., "always fails at retry #15")

## Performance Impact

### Before
```
Phase 1 (logs):     ~30s   (sequential per service)
Phase 2 (SQS):      ~360s  (waits for CloudWatch lag)
Phase 3 (Kinesis):  ~420s  (CloudWatch lag + buffer)
────────────────────────────────────
Subtotal:           ~810s (13.5 minutes)
```

### After
```
Phase 1 (logs):     ~30s   (unchanged)
Phase 2 (SQS):      ~10s   (5-10s SQS API polling, no CloudWatch wait)
Phase 3 (Kinesis):  ~30s   (if data arrives, polling catches it)
────────────────────────────────────
Subtotal:           ~70s   (1.2 minutes)
```

**Expected Reduction:** ~740 seconds (~12+ minutes per deploy)

### In Normal Operating Conditions
- If ECS containers start and emit data: **SQS phase finishes in <20 seconds**
- If there's a schema error: **DLQ catches it in <10 seconds**
- If CloudWatch metrics needed as fallback: Still works, just slower path

## Backward Compatibility

- All environment variables supported: `WAIT_PHASE1_SECS`, `POLL_INTERVAL`, etc.
- Fallback to CloudWatch metrics still works if SQS fast-path fails
- Can be tested side-by-side: old script stays in place
- Gradual rollout: Test in HML first, then use in production if stable

## Migration Path

1. **Week 1:** Deploy new script to HML test workflow (background validation)
2. **Week 2:** Compare timing with old script, gather metrics
3. **Week 3:** Switch main workflow to use optimized script if results are positive
4. **Week 4:** Remove old script from codebase

## Testing

### Local Test (DEV environment)
```bash
bash scripts/hml_integration_test_optimized.sh
```

### CI Test (HML environment)
Update `.github/workflows/deploy_all_dm_applications.yml` line 532:
```yaml
# Before
if bash scripts/hml_integration_test.sh 2>&1 | tee /tmp/hml_stream_test.txt; then

# After
if bash scripts/hml_integration_test_optimized.sh 2>&1 | tee /tmp/hml_stream_test.txt; then
```

## Metrics to Monitor

After rollout, watch for:
- ✅ **Phase 2 elapsed time:** Should drop from 360s → 10-30s
- ✅ **DLQ errors caught:** Should see "DLQ has X rejected messages" if schema breaks
- ✅ **Overall deploy time:** Should drop by ~12 minutes
- ⚠️ **False negatives:** Shouldn't see more Phase 2 failures (should be fewer)

## Fallback

If optimized script shows issues:
1. Can revert to old script immediately
2. Or add `WAIT_PHASE1_SECS=360` env var to restore old behavior
3. Both scripts coexist peacefully
