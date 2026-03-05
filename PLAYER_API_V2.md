# PLAYER API V2

## 1. Create Slot
`POST /v2/game/slots`

Request:
```json
{
  "slot_name": "新冒险",
  "world_seed": "optional-seed",
  "canon_gen": 9,
  "canon_game": "sv",
  "player_profile": {
    "name": "可选",
    "gender": "可选",
    "age": 18,
    "height_cm": 170
  }
}
```

## 2. Get Slot
`GET /v2/game/slots/{slot_id}`

Returns slot snapshot, turns, party, inventory, and kernel summaries.

## 3. Turn (Stream)
`POST /v2/game/slots/{slot_id}/turns`

Body:
```json
{
  "text": "我选择水跃鱼作为初始伙伴",
  "stream": true,
  "language": "zh",
  "pace": "balanced",
  "client_turn_id": "optional-idempotency-key"
}
```

SSE events:
- `ack`
- `primary`
- `delta`
- `done`
- `error`

`done` payload includes:
- `turn_id`
- `turn_index`
- `narrative.primary`
- `narrative.detail` (optional)
- `action_options` (final actions, render now)
- `state_snapshot`
- `timings`
- `injection_stats`

## 4. Execute Action
`POST /v2/game/slots/{slot_id}/actions/{action_id}`

Same stream contract as turn.

## 5. Kernel Read APIs
- `GET /v2/game/slots/{slot_id}/lore`
- `GET /v2/game/slots/{slot_id}/time`
- `GET /v2/game/slots/{slot_id}/factions`

## Notes
- `/v1/*` APIs are removed.
- For local desktop play, no explicit login is required when `AUTH_BYPASS_LOCAL=true`.
