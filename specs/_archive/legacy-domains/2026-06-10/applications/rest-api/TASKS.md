# Tasks: REST API — Gold Layer Serving

> **Spec:** `specify/specs/rest-api/SPEC.md`  
> **Plan:** `specify/specs/rest-api/PLAN.md`  
> **Branch:** `feature/rest-api-serving`

---

## Pre-Implementation Checklist

- [ ] SPEC.md reviewed and approved by product owner
- [ ] PLAN.md reviewed and approved by lead engineer
- [ ] Databricks SQL Warehouse ID confirmed (PRD)
- [ ] SSM Parameter Store paths agreed: `/dd-chain-explorer/rest-api/databricks-host`, `/databricks-token`, `/warehouse-id`
- [ ] Branch created: `feature/rest-api-serving` from `develop`

---

## Phase 1: Foundation

- [x] **T01**: Create `apps/rest-api/` directory structure + `Dockerfile` + `requirements.txt`
  - *Verification:* `docker build apps/rest-api/` succeeds without errors

- [x] **T02**: Create `src/config.py` with Pydantic `Settings` class — reads all env vars
  - *Verification:* `python -c "from src.config import settings; print(settings.databricks_host)"` does not raise

- [x] **T03**: Create `src/databricks_client.py` — `DatabricksSQLClient` wrapping SQL Statement API
  - Methods: `execute_query(sql: str) -> list[dict]`, `ping() -> bool`
  - *Verification:* Unit test with mocked HTTP client returns expected dict list

- [x] **T04**: Create Pydantic response models in `src/models/response_models.py`
  - Models: `NetworkMetricsRecord`, `PopularContractRecord`, `GasAnalyticsRecord`, `GasTypesRecord`, `HealthResponse`, `PaginatedResponse[T]`
  - *Verification:* `python -c "from src.models.response_models import PaginatedResponse"` does not raise

- [x] **T05**: Create `src/models/request_models.py` — query parameter models with validation
  - Models: `DateRangeParams`, `PaginationParams`, `ContractFilterParams`
  - *Verification:* Unit test: passing `page_size=200` raises `422` equivalent (Pydantic validation error)

---

## Phase 2: Application Core

- [x] **T06**: Create `src/main.py` — FastAPI app with lifespan, middleware registration, router includes
  - *Verification:* `uvicorn src.main:app --port 8080` starts without errors

- [x] **T07**: Create `src/middleware/logging_middleware.py` — structured request/response logging to CloudWatch
  - *Verification:* Each request produces a structured JSON log entry with `request_id`, `method`, `path`, `status_code`, `latency_ms`

- [x] **T08**: Create `src/middleware/cors_middleware.py` — CORS headers (`Access-Control-Allow-Origin: *`)
  - *Verification:* `curl -H "Origin: http://example.com"` includes CORS header in response

- [x] **T09**: Create `src/routers/health.py` — `GET /health` endpoint
  - *Verification:* `GET /health` returns `200` with `{"status": "healthy", "version": "..."}` when Databricks reachable; returns `503` when not reachable

- [x] **T10**: Create `src/routers/network.py` — `GET /api/v1/network/metrics`
  - SQL: `SELECT * FROM {catalog}.g_network.network_metrics_hourly WHERE hour_bucket >= {from_ts} ... ORDER BY hour_bucket DESC LIMIT {page_size} OFFSET ...`
  - *Verification:* Response matches `PaginatedResponse[NetworkMetricsRecord]` schema; `from_ts`/`to_ts` filtering works

- [x] **T11**: Create `src/routers/contracts.py` — `GET /api/v1/contracts/popular`
  - *Verification:* Response is list of `PopularContractRecord`; `limit=5` returns exactly 5 records; `min_tx_count` filters correctly

- [x] **T12**: Create `src/routers/gas.py` — `GET /api/v1/gas/analytics` + `GET /api/v1/gas/types`
  - *Verification:* Both endpoints return correct schema; `type` filter on `/gas/analytics` returns only matching rows

---

## Phase 3: Testing

- [ ] **T13**: Write unit tests for `DatabricksSQLClient` with mocked responses
  - *Verification:* `pytest tests/test_databricks_client.py` — 100% pass

- [ ] **T14**: Write unit tests for all router functions with mocked `DatabricksSQLClient`
  - *Verification:* `pytest tests/test_routers.py` — all endpoints tested for happy path + error cases

- [ ] **T15**: Write integration test script `scripts/test_rest_api.sh`
  - Tests: `/health`, all 4 analytics endpoints, invalid input returns `400`/`422`
  - *Verification:* Script runs against deployed HML instance and all checks pass

---

## Phase 4: Infrastructure

- [ ] **T16**: Create ECR repository `dm-rest-api` in `services/prd/07_ecs/rest_api_ecr.tf`
  - *Verification:* `terraform plan` shows new ECR resource; `terraform apply` creates it

- [ ] **T17**: Create ECS task definition + service for `dm-rest-api` in `services/prd/07_ecs/rest_api_service.tf`
  - Task: 512 CPU / 1024 MB, port 8080, SSM secrets
  - *Verification:* ECS task definition registered; service reaches RUNNING state

- [ ] **T18**: Create ALB + target group + HTTPS listener in `services/prd/02_vpc/alb.tf`
  - *Verification:* `curl https://{alb-dns}/health` returns `200`

- [ ] **T19**: Create SSM Parameters for Databricks credentials (REST API scope)
  - *Verification:* `aws ssm get-parameter --name /dd-chain-explorer/rest-api/databricks-host` returns value

---

## Phase 5: CI/CD Integration

- [ ] **T20**: Add `deploy_rest_api` sub-pipeline to `deploy_all_dm_applications.yml`
  - Steps: build Docker, push ECR, deploy ECS, run integration test
  - *Verification:* Workflow runs end-to-end in HML; all integration test checks pass

- [ ] **T21**: Update `makefile` with `rest_api_*` targets for local development
  - *Verification:* `make deploy_dev_rest_api` starts FastAPI locally; `make stop_dev_rest_api` stops it

---

## Phase 6: Documentation

- [ ] **T22**: Update `README.md` — add REST API section with endpoint reference and deployment instructions
  - *Verification:* README accurately describes API and how to access it

- [ ] **T23**: Update `specify/memory/product.md` — add REST API to Data Serving section
  - *Verification:* File updated; spec-anchored product description is current

---

## Definition of Done

- All tasks checked off
- All unit tests passing (`pytest` 100% green)
- Integration test `scripts/test_rest_api.sh` passing in HML
- `/health` endpoint responds in < 200ms
- All analytics endpoints respond in < 2000ms under light load
- SPEC.md updated if implementation diverged from spec intent
- PR reviewed and approved
- Deployed to PRD with `v{VERSION}-api` git tag
