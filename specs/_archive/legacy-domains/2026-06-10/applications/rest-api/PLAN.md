# Plan: REST API — Gold Layer Serving

> **Spec:** `specify/specs/rest-api/SPEC.md`  
> **Branch:** `feature/rest-api-serving`  
> **Status:** Not started

---

## Technology Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Framework | FastAPI + Uvicorn | Async support, Pydantic validation, OpenAPI docs auto-generated |
| Language | Python 3.12 | Consistent with rest of codebase |
| Data source | Databricks SQL Statement API | Reuses existing SQL Warehouse; no new database |
| Deployment | ECS Fargate (`07_ecs` Terraform module) | Reuses existing cluster and VPC |
| Container | `python:3.12-slim` | Consistent with streaming app base image |
| Logging | `CloudWatchLoggingHandler` (dm-chain-utils) | Consistent with streaming jobs |
| Health check | FastAPI endpoint + ECS health check | ALB target group health check |

---

## Architecture

```
Client (Browser / Dashboard / etc.)
    │  HTTPS
    ▼
AWS Application Load Balancer
    │
    ▼
ECS Fargate — rest-api service (FastAPI, port 8080)
    │  HTTP (Databricks SQL Statement API)
    ▼
Databricks SQL Warehouse (PRD)
    │  reads from
    ▼
Gold MVs: g_network, g_apps (pre-aggregated, low-latency queries)
```

---

## Directory Structure

```
apps/rest-api/
  Dockerfile
  requirements.txt
  src/
    main.py                  # FastAPI app + lifespan + middleware
    config.py                # Settings (env vars, Pydantic BaseSettings)
    databricks_client.py     # Databricks SQL Statement API wrapper
    routers/
      health.py              # GET /health
      network.py             # GET /api/v1/network/metrics
      contracts.py           # GET /api/v1/contracts/popular
      gas.py                 # GET /api/v1/gas/analytics + /gas/types
    models/
      request_models.py      # Query parameter models
      response_models.py     # Pydantic response schemas
    middleware/
      logging_middleware.py  # Request/response structured logging
      cors_middleware.py     # CORS headers
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABRICKS_HOST` | Yes | Databricks workspace URL |
| `DATABRICKS_TOKEN` | Yes | SQL Warehouse access token (or OAuth M2M) |
| `DATABRICKS_WAREHOUSE_ID` | Yes | SQL Warehouse ID for query execution |
| `DATABRICKS_CATALOG` | Yes | Catalog name (`dd_chain_explorer` in PRD, `dev` in DEV) |
| `CLOUDWATCH_LOG_GROUP` | Yes | CloudWatch log group for API request logs |
| `PORT` | No | Uvicorn port (default: 8080) |
| `LOG_LEVEL` | No | Logging level (default: INFO) |

---

## Databricks SQL Statement API Contract

```python
# POST https://{workspace-host}/api/2.0/sql/statements
{
  "warehouse_id": "{warehouse_id}",
  "statement": "SELECT * FROM {catalog}.g_network.network_metrics_hourly WHERE ...",
  "wait_timeout": "10s",
  "on_wait_timeout": "CANCEL"
}
```

---

## API Endpoint Mapping to SQL Queries

| Endpoint | SQL Query | Estimated Latency |
|---|---|---|
| `GET /api/v1/network/metrics` | `SELECT * FROM {catalog}.g_network.network_metrics_hourly WHERE hour_bucket >= ... ORDER BY hour_bucket DESC LIMIT {page_size} OFFSET {offset}` | < 500ms (MV pre-aggregated) |
| `GET /api/v1/contracts/popular` | `SELECT * FROM {catalog}.g_apps.popular_contracts_ranking ORDER BY tx_count DESC LIMIT {limit}` | < 500ms |
| `GET /api/v1/gas/analytics` | `SELECT * FROM {catalog}.g_apps.gas_price_distribution_hourly WHERE ...` | < 500ms |
| `GET /api/v1/gas/types` | `SELECT type_transaction, count(*) as tx_count FROM {catalog}.g_apps.ethereum_gas_consume WHERE ... GROUP BY type_transaction` | < 1s |

---

## Terraform Changes Required

### New ECS Task Definition (`07_ecs`)

```hcl
# services/prd/07_ecs/rest_api_task.tf
resource "aws_ecs_task_definition" "rest_api" {
  family                   = "dm-rest-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  
  container_definitions = jsonencode([{
    name  = "rest-api"
    image = "${aws_ecr_repository.rest_api.repository_url}:latest"
    portMappings = [{ containerPort = 8080 }]
    environment = [
      { name = "DATABRICKS_CATALOG", value = "dd_chain_explorer" }
    ]
    secrets = [
      { name = "DATABRICKS_HOST",          valueFrom = aws_ssm_parameter.databricks_host.arn },
      { name = "DATABRICKS_TOKEN",         valueFrom = aws_ssm_parameter.databricks_token.arn },
      { name = "DATABRICKS_WAREHOUSE_ID",  valueFrom = aws_ssm_parameter.warehouse_id.arn }
    ]
  }])
}
```

### New ALB (Application Load Balancer)

A new ALB shall route public HTTPS traffic to the ECS service. The ALB shall be provisioned in the `02_vpc` module's public subnets.

### New ECR Repository

ECR repository `dm-rest-api` for the FastAPI Docker image.

---

## Security Considerations

- Databricks token/credentials stored in AWS SSM Parameter Store — NOT in ECS environment variables directly
- ECS task role grants: SSM GetParameter (scoped to `/dd-chain-explorer/rest-api/*`)
- ALB HTTPS only (port 443) — redirect HTTP to HTTPS
- No public RDS, no persistent database — Databricks is the only data source
- CORS wildcard (`*`) for v1 — restrict in v2 when authentication is added

---

## Performance Considerations

- Gold MVs are pre-aggregated — queries should return in < 500ms on a running Serverless SQL Warehouse
- No caching in v1 (add Redis in v2 if latency SLA not met)
- SQL Warehouse auto-starts on first query; cold start adds up to 60s — health check warms the warehouse
- `page_size` capped at 168 (1 week of hourly data) to prevent large result sets
