# Changelog

## 0.3.0 - 2026-03-03

- Breaking: V1 API and V1 dashboard routes are removed; project is V2-only.
- Default model switched to GLM5:
  - `XF_MODEL_ID=xopglm5`
  - remember to use matching `XF_APPID/XF_API_KEY/XF_API_SECRET`
- V2 stream UX adjusted:
  - event order now targets text-first rendering
  - action buttons are rendered from `done.action_options` only
- Removed detail expand rendering from player chat bubbles; single text flow display.
- Strengthened JSON leakage filtering in both backend stream sanitizer and frontend SSE sanitizer.
- Adventure create flow now shows explicit progress states and readable error messages.
- Desktop launcher improvements:
  - single instance lock
  - health-check based service reuse on ports 8000/3000
  - no token/login bootstrap dependency for desktop adventure entry
- Added startup observability field: `model_id`.

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
