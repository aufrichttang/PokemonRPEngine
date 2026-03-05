# API (V2 Only)

## Base
- Local: `http://127.0.0.1:8000`

## Health
- `GET /healthz`
- `GET /readyz`
- `GET /metrics`

## Game Slots
- `POST /v2/game/slots`
- `GET /v2/game/slots`
- `GET /v2/game/slots/{slot_id}`
- `GET /v2/game/slots/{slot_id}/lore`
- `GET /v2/game/slots/{slot_id}/time`
- `GET /v2/game/slots/{slot_id}/factions`
- `GET /v2/game/slots/{slot_id}/export`

## Turns (SSE)
- `POST /v2/game/slots/{slot_id}/turns`
- `POST /v2/game/slots/{slot_id}/actions/{action_id}`

`stream=true` 时使用 SSE，事件顺序：
1. `ack`
2. `primary`
3. `delta` (0..N)
4. `done`
5. `error`（异常时）

说明：动作按钮以 `done.action_options` 为准，不在中途展示。

## Deprecated / Removed
- 全部 `/v1/*` 已下线。
