# Security

## Secret Management

- All secrets are environment variables.
- Never store API keys in DB or source code.
- `.env.example` contains placeholders only.

Required production secrets:

- `JWT_SECRET` (>=32 chars)
- `XF_APPID`
- `XF_API_KEY`
- `XF_API_SECRET`

## Logging & Redaction

- Logs are structured JSON.
- Sensitive keys are redacted (`authorization`, `xf_api_secret`, `xf_api_key`, `password`, `jwt_secret`).
- Do not log full upstream auth headers.

## Access Control

- JWT bearer authentication for all protected endpoints.
- RBAC roles: `admin`, `operator`, `viewer`, `user`.
- Memory debug/confirm endpoints require `admin|operator`.
- Admin frontend stores token in `sessionStorage` (non-persistent browser session).
- Configure `CORS_ALLOWED_ORIGINS` explicitly in production; do not use wildcard in internet-facing env.

## Rate Limiting

- Per-user + endpoint throttling.
- Redis-backed sliding window with in-memory fallback.

## Data Governance

- Session delete endpoint supports GDPR-like removal workflow.
- Audit logging can be content-controlled by `AUDIT_CONTENT_ENABLED`.

## Key Rotation

1. Rotate keys in Xfyun console.
2. Update env vars and restart deployment.
3. Invalidate old credentials and monitor error rates.
