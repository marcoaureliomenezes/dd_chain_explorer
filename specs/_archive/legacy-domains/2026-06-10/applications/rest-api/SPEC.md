# Spec: REST API — Gold Layer Serving

> **Type:** Spec-First (planned feature — ROADMAP TODO-S06 + TODO-S10)  
> **Priority:** P3 (Phase 3 — Platform Evolution)  
> **Depends on:** `specs/medallion-dlt/SPEC.md` (Gold MVs must be running)  
> **Status:** Not implemented — spec written 2026-04

---

## Overview

A REST API that exposes the Gold-layer Databricks tables as HTTP endpoints for external consumption — dashboards, third-party analytics tools, or a public-facing Ethereum analytics web page (TODO-S10). The API serves pre-aggregated analytics data from the Gold MVs and provides query flexibility through pagination and filtering parameters.

---

## Discovery Interview (Answered)

**Q: Who consumes this API?**  
A: Initially internal (replace dashboard → API → dashboard pattern). Eventually public (see TODO-S10).

**Q: Is authentication required?**  
A: No authentication for v1 (public API). Add API key auth in a future version.

**Q: What data needs to be served?**  
A: Gold MV data: network metrics, popular contracts, gas analytics, P2P transfers. Not raw Bronze/Silver data.

**Q: What is the acceptable query latency?**  
A: < 2 seconds for all endpoints under normal load.

**Q: Where should the API run?**  
A: Options: FastAPI on ECS Fargate (most control), OR Databricks SQL Statement API (no new infrastructure). Decision: FastAPI on ECS — reuses existing ECS infrastructure.

**Q: What pagination model?**  
A: Page-based (`page`, `page_size`). No cursor-based for v1.

**Q: What response format?**  
A: JSON only. No CSV, Parquet, or GraphQL for v1.

---

## User Stories

### US-001: Network Health Dashboard

As a data consumer, I want to retrieve hourly Ethereum network metrics so that I can display TPS, gas prices, and block production health on a dashboard without running Databricks queries.

**Acceptance Criteria:**
- Given a GET request to `/api/v1/network/metrics`, when the request is valid, then the system shall return the last 24 hours of `g_network.network_metrics_hourly` data in descending timestamp order.
- Given a `from_ts` and `to_ts` query parameter, when provided, then the system shall filter results to the specified UTC timestamp range.
- Given a `page` and `page_size` parameter, when provided, then the system shall return only the corresponding page of results with `total_count`, `page`, `page_size`, and `has_next` in the response envelope.

### US-002: Popular Contracts Lookup

As a data consumer, I want to retrieve the most active Ethereum contracts in the last hour so that I can display a hot contracts leaderboard.

**Acceptance Criteria:**
- Given a GET request to `/api/v1/contracts/popular`, when the request is valid, then the system shall return the top N contracts from `g_apps.popular_contracts_ranking` ordered by `tx_count` descending.
- Given a `limit` query parameter (default 10, max 100), when provided, then the system shall limit the result set accordingly.
- Given a `min_tx_count` query parameter, when provided, then the system shall filter contracts with fewer transactions than the threshold.

### US-003: Gas Analytics

As a data consumer, I want to retrieve Ethereum gas consumption metrics so that I can display gas price trends and transaction type breakdowns.

**Acceptance Criteria:**
- Given a GET request to `/api/v1/gas/analytics`, when the request is valid, then the system shall return data from `g_apps.gas_price_distribution_hourly` for the last 24 hours.
- Given a `type` query parameter (`contract_deploy`, `peer_to_peer`, `contract_interaction`), when provided, then the system shall filter `g_apps.ethereum_gas_consume` by transaction type.

### US-004: API Health

As an operator, I want a health check endpoint that confirms the API and its data sources are operational.

**Acceptance Criteria:**
- Given a GET request to `/health`, then the system shall return `200 OK` with a JSON body `{"status": "healthy", "version": "{VERSION}"}` when the API can connect to the Databricks SQL Warehouse.
- Given the Databricks SQL Warehouse is unavailable, when `/health` is called, then the system shall return `503 Service Unavailable` with `{"status": "degraded", "error": "data source unavailable"}`.

---

## Functional Requirements

**FR-API-001 — Base URL Structure**  
The system shall expose all analytics endpoints under `/api/v1/` prefix. The version prefix enables non-breaking future API evolution.

**FR-API-002 — Network Metrics Endpoint**  
`GET /api/v1/network/metrics`  
- Query parameters: `from_ts` (ISO 8601 UTC, optional), `to_ts` (ISO 8601 UTC, optional), `page` (int, default 1), `page_size` (int, default 24, max 168)  
- Response: paginated list of `network_metrics_hourly` records

**FR-API-003 — Popular Contracts Endpoint**  
`GET /api/v1/contracts/popular`  
- Query parameters: `limit` (int, default 10, max 100), `min_tx_count` (int, optional)  
- Response: list of popular contracts with `contract_address`, `tx_count`, `unique_senders`, `first_seen`, `last_seen`

**FR-API-004 — Gas Analytics Endpoint**  
`GET /api/v1/gas/analytics`  
- Query parameters: `from_ts`, `to_ts`, `type` (string enum, optional)  
- Response: list of gas price distribution records from `g_apps.gas_price_distribution_hourly`

**FR-API-005 — Gas Transaction Type Distribution**  
`GET /api/v1/gas/types`  
- Response: aggregated counts of `contract_deploy`, `peer_to_peer`, `contract_interaction` transactions from `g_apps.ethereum_gas_consume` for the last 24 hours

**FR-API-006 — Health Check Endpoint**  
`GET /health`  
- Response: `{"status": "healthy" | "degraded", "version": string, "error": string (only if degraded)}`

**FR-API-007 — Standard Response Envelope**  
All list endpoints shall return responses in this envelope:
```json
{
  "data": [...],
  "total_count": 100,
  "page": 1,
  "page_size": 24,
  "has_next": true
}
```

**FR-API-008 — Error Response Format**  
All error responses shall follow this format:
```json
{
  "error": "Human-readable error message",
  "code": "ERROR_CODE",
  "request_id": "uuid"
}
```

**FR-API-009 — CORS Headers**  
The system shall include CORS headers allowing access from any origin (`Access-Control-Allow-Origin: *`) for v1 (public API, no authentication).

**FR-API-010 — Input Validation**  
If `from_ts` or `to_ts` are not valid ISO 8601 timestamps, the system shall return `400 Bad Request` with a descriptive error message. If `page_size` exceeds the maximum, the system shall return `422 Unprocessable Entity`.

---

## Non-Functional Requirements

**NFR-API-001 — Response Latency**  
The system shall respond to 95% of requests within 2,000ms under a load of 50 concurrent users.

**NFR-API-002 — Data Source**  
All analytics data shall be read exclusively from Databricks Gold layer via the Databricks SQL Statement API (HTTP) — the API shall NOT query Bronze or Silver tables directly.

**NFR-API-003 — No Database in API**  
The API shall have no persistent database of its own. It is a thin read-only proxy over Databricks SQL.

**NFR-API-004 — Deployment on ECS Fargate**  
The API shall be deployed as a Docker container on ECS Fargate in the existing PRD VPC and ECS cluster, reusing the `07_ecs` Terraform module.

**NFR-API-005 — Framework: FastAPI**  
The API shall be implemented in Python using FastAPI with Pydantic models for request/response validation.

**NFR-API-006 — No Authentication (v1)**  
v1 requires no authentication. API keys or OAuth will be added in a future spec if public consumption requires rate limiting.

**NFR-API-007 — Observability**  
All API requests shall be logged to CloudWatch Logs via `CloudWatchLoggingHandler` from `dm-chain-utils`. Request logs shall include: `request_id`, `method`, `path`, `query_params`, `status_code`, `latency_ms`.

---

## API Contract Summary

| Method | Path | Description | Source Table |
|---|---|---|---|
| `GET` | `/health` | Health check | (Databricks ping) |
| `GET` | `/api/v1/network/metrics` | Hourly network KPIs | `g_network.network_metrics_hourly` |
| `GET` | `/api/v1/contracts/popular` | Top contracts by volume | `g_apps.popular_contracts_ranking` |
| `GET` | `/api/v1/gas/analytics` | Gas price distribution | `g_apps.gas_price_distribution_hourly` |
| `GET` | `/api/v1/gas/types` | Transaction type breakdown | `g_apps.ethereum_gas_consume` |

---

## Out of Scope (v1)

- Authentication or API key management
- Write endpoints (API is read-only)
- Streaming/WebSocket endpoints
- Bronze or Silver data access
- GraphQL interface
- Public web frontend (TODO-S10 — depends on this spec)
- Rate limiting
- Caching layer (Redis, ElastiCache)
- Multi-region deployment
