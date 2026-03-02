# Architecture

## Overview

Pokemon RP Engine uses a split frontend/backend architecture:

- Frontend Console (`web/`): Next.js 15 + Ant Design
- Backend API (`app/`): FastAPI + SQLAlchemy + memory pipeline + provider abstraction

Backend follows a layered structure:

- API Layer (`app/api`): auth, sessions, chat, admin/debug, health, metrics
- Service Layer (`app/services`): application workflows and transaction boundaries
- Memory Layer (`app/memory`): query planning, retrieval, compression, prompt assembly, write-back
- Canon Layer (`app/canon`): structured fact extraction/checking and canon ingest/validation
- Provider Layer (`app/providers`): LLM provider abstraction and Xfyun integrations
- Data Layer (`app/db`): SQLAlchemy models + Alembic migrations

## Admin Console Modules

- `sessions`: 会话列表、创建、删除、导出
- `sessions/[id]`: 聊天窗口 + SSE 流式输出 + 记忆调试 + 冲突确认
- `ops`: 聚合指标面板（JSON summary + health/ready）
- `canon`: Pokemon/Move 检索与属性克制表查询

## Core Chat Flow

1. `POST /v1/sessions/{id}/messages`
2. `QueryBuilder` generates 3-6 retrieval queries
3. `MemoryRetriever` fetches:
   - confirmed timeline facts
   - vector recalls (session-scoped)
   - open threads
4. `Compression` applies count and budget limits
5. `PromptAssembler` builds stable prompt blocks:
   - `CANON_FACTS`
   - `RELEVANT_RECALLS`
   - `OPEN_THREADS`
   - `SHORT_WINDOW`
6. Provider generates assistant text (`mock/http/ws`)
7. `CanonFactChecker` validates `facts_used[]` against canon DB
8. Optional repair generation on mismatch
9. `MemoryWriter` writes timeline updates, vector chunks, conflict/open thread records
10. Turn is committed and auditable

## Data Design

- `timeline_events` is append-only semantics for facts
- `canon_level=confirmed` is treated as immutable truth source
- conflicts are never overwrite operations; they create `conflict` events + `open_threads`
- `audit_logs` records replayable internal decisions and prompt injection snapshots

## Extensibility

- Add new LLM providers by implementing `LLMProvider`
- Replace embedding provider via `EMBEDDING_PROVIDER` env
- Add custom world lore via separate tables, without overriding canon tables
- Add battle engine as deterministic service using `canon_type_chart`

## Observability

- `trace_id` middleware and `X-Trace-Id` response header
- request latency header: `X-Process-Time-Ms`
- JSON logs via `structlog`
- local log file output (`LOG_FILE_PATH`, default `logs/rp-engine.log`)
- Prometheus metrics:
  - `rp_requests_total`
  - `rp_provider_latency_seconds`
  - `rp_retrieval_vector_hits_total`
  - `rp_retrieval_timeline_hits_total`
  - `rp_turns_created_total`
  - `rp_conflicts_total`
- Admin summary endpoint:
  - `GET /v1/admin/metrics/summary`
  - `GET /v1/admin/logs/recent`

## New API Additions for Console

- `GET /v1/sessions/{id}/timeline/events`
- `GET /v1/canon/pokemon`
- `GET /v1/canon/moves`
- `GET /v1/canon/type-chart`
- `GET /v1/admin/metrics/summary`
