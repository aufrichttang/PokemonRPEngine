# Lore Kernel Integration (V2)

## Goal
Integrate whitepaper-aligned **Lore Kernel / Time Kernel / Faction Kernel** into Pokemon RP V2 as deterministic backend state.

## Scope
- Add 3 kernel state tables (1:1 with `save_slots`)
- Extend memory/timeline metadata for time-class and legacy tags
- Apply deterministic mutation on every turn
- Expose kernel summaries from `/v2/game/slots/{slot_id}`

## Data flow
1. User action (button or free text) enters turn pipeline.
2. LLM generates narration + optional action options.
3. Backend writes turn + memory chunks + timeline events.
4. `StoryStateEngine.apply_story_outcome()` mutates kernel states.
5. `StateReducer` syncs slot aggregates.
6. V2 aggregate endpoint returns kernel summaries + warnings.

## Deterministic mutation rule
- LLM does not mutate kernel state directly.
- Backend applies keyword/battle/progress-based deltas.
- `cycle_instability` maps to `protocol_phase` by rule thresholds.

## Memory classification
Each timeline/memory item stores:
- `time_class`: fixed / fragile / unjudged / echo
- `source_trust`
- `witness_count`
- `narrative_conflict_score`
- `canon_legacy_tags`

RAG retrieval supports filtering by `time_class` and `canon_legacy_tags`.

## Compatibility policy
- New slots use `schema_version = 3`.
- Slots with `schema_version < 3` are considered legacy and rejected by V2 slot APIs.
- Use helper scripts:
  - `scripts/mark_legacy_slots_readonly.py`
  - `scripts/create_v3_slot_from_profile.py`

