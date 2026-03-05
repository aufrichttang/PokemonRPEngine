# Architecture

## Overview
Pokemon RP Engine 采用前后端分离：
- Frontend (`web/`): Next.js 15
- Backend (`app/`): FastAPI + SQLAlchemy
- Desktop (`desktop/`): Electron

## Backend Layers
- API Layer: `app/api`（auth / sessions / chat / v2 game / admin）
- Service Layer: `app/services`（业务编排、事务边界）
- Memory Layer: `app/memory`（query/retrieve/compress/assemble/writeback）
- Canon Layer: `app/canon`（事实校验与数据导入）
- Kernel Layer: `app/kernels`（lore/time/faction）
- World Layer: `app/worldgen`（seed 生成）
- Data Layer: `app/db`（模型 + 迁移）

## Runtime Flow (V2)
1. `POST /v2/game/slots/{slot_id}/turns?stream=true`
2. `TurnPipelineService` 执行两阶段：
   - Planner：生成正式 `action_options` + `narrative.primary`
   - Narrative：流式生成 detail
3. SSE 固定序列：`ack -> options -> primary -> delta* -> done`
4. `state_reducer` 统一落库（状态快照、回合记录、内核摘要）
5. `memory_writer` 写入 timeline/memory chunks

## No-Map Design (Breaking)
本版本已下线地图功能：
- 玩家 API 不再提供 `/map` 路由
- `world_profile` 与 `v2 slot detail` 不再返回 `map_data`
- 章节推进仅通过 `story_progress` + 内核压力驱动

## Memory + Canon
- Timeline（confirmed/implied/pending/conflict）
- Vector memory chunks
- Prompt 注入顺序：
  - `CANON_FACTS`
  - `PLAYER_PROFILE`
  - `WORLD_PROFILE`
  - `KERNEL_CAPSULE`
  - `STORY_ENHANCEMENT`
  - `STORY_BLUEPRINT`
  - `CURRENT_CHAPTER_OBJECTIVE`
  - `LEGENDARY_WEB`
  - `SACRIFICE_STAKES`
  - `ROMANCE_CANDIDATES`
  - `STARTER_OPTIONS`
  - `GYM_PLAN`
  - `RELEVANT_RECALLS`
  - `OPEN_THREADS`
  - `SHORT_WINDOW`

## Option Strategy
- 优先 planner 生成（质量优先）
- planner 超时/失败时走 `contextual_fallback`（基于 objective/location/quest/user input）
- 不再使用固定三模板 `opt-mainline/opt-investigate/opt-prepare`

## JSON Leak Guard
双层防护：
- 后端流式阶段在 `facts_used/state_update/...` 标记处截断 delta
- 前端 stream 消费再做 sanitize

## Observability
- `trace_id` + `X-Trace-Id`
- JSON logs (`structlog`)
- Metrics:
  - `rp_turn_first_interactive_seconds`
  - `rp_turn_done_seconds`
  - `rp_provider_planner_latency_seconds`
  - `rp_provider_narrative_latency_seconds`
  - `rp_planner_timeout_fallback_total`

## Dev/Player Modes
- 玩家默认隐藏调试面板
- 开发模式：`RP_DEV_DEBUG_UI=true` 或 `?debug=1`
