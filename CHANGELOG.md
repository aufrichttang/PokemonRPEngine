# Changelog

## 0.2.0 - 2026-02-28

- Added official admin console in `web/` (Next.js 15 + Ant Design)
- Implemented frontend pages for login, sessions, SSE chat, memory debug, ops, and canon workbench
- Added backend endpoints:
  - `GET /v1/sessions/{id}/timeline/events`
  - `GET /v1/canon/pokemon`
  - `GET /v1/canon/moves`
  - `GET /v1/canon/type-chart`
  - `GET /v1/admin/metrics/summary`
- Added CORS configuration (`CORS_ALLOWED_ORIGINS`)
- Added admin role promotion script (`scripts/promote_role.py`)

## 0.1.0 - 2026-02-28

- Initial enterprise scaffold for Pokemon RP engine
- Implemented FastAPI APIs, auth, RBAC, and session management
- Added memory pipeline with timeline/vector/open-thread channels
- Added provider abstraction with mock/http/ws implementations
- Added canon fact checker and canon ingest/validate scripts
- Added Prometheus metrics, trace middleware, JSON logging, and rate limiting
- Added Docker Compose stack and Kubernetes deployment manifests
- Added unit/integration tests and CI workflow
