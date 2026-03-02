# API

## Auth

### POST /v1/auth/register
Request:

```json
{"email":"user@example.com","password":"Password123!"}
```

Response:

```json
{"id":"<uuid>","email":"user@example.com","role":"user"}
```

### POST /v1/auth/login
Response:

```json
{"access_token":"<jwt>","token_type":"bearer"}
```

## Sessions

### POST /v1/sessions
Create session.

### GET /v1/sessions
Paginated list.

### GET /v1/sessions/{id}
Session details + recent turns.

### GET /v1/sessions/{id}/timeline/events
List timeline events for conflict/pending review.

Query:
- `canon_level`: `confirmed|implied|pending|conflict` (optional)
- `page`, `size`

### DELETE /v1/sessions/{id}
Soft delete.

### GET /v1/sessions/{id}/export?fmt=json|markdown
Export session data (GDPR-like portability).

## Chat

### POST /v1/sessions/{id}/messages
Request:

```json
{"text":"继续剧情","stream":false}
```

Non-stream response:

```json
{
  "turn_id":"<uuid>",
  "turn_index":1,
  "assistant_text":"...",
  "provider_latency_ms":120,
  "token_usage":{"prompt_tokens":100,"completion_tokens":120}
}
```

Stream response (`text/event-stream`):

```text
event: delta
data: {"turn_id":"","text":"..."}

event: done
data: {"turn_id":"<uuid>","turn_index":12,"usage":{}}

event: error
data: {"code":"stream_internal_error","message":"..."}
```

## Admin

### GET /v1/sessions/{id}/memory/debug
Role: `admin|operator`

Response includes:
- `query_plan`
- `retrieval`
- `prompt_injection`

### POST /v1/sessions/{id}/memory/confirm
Role: `admin|operator`

Request:

```json
{"event_id":"<uuid>","confirm":true,"note":"用户确认"}
```

## Ops

- `GET /healthz`
- `GET /readyz`
- `GET /metrics`
- `GET /v1/admin/metrics`
- `GET /v1/admin/metrics/summary` (admin/operator, JSON summary)
- `GET /v1/admin/logs/recent?lines=200` (admin/operator, recent structured logs)

## Canon

### GET /v1/canon/pokemon
Query:
- `q` (name/slug/alias, optional)
- `generation` (optional)
- `page`, `size`

### GET /v1/canon/moves
Query:
- `q` (name/slug/alias, optional)
- `generation` (optional)
- `page`, `size`

### GET /v1/canon/type-chart
Query:
- `generation` (default `9`)
