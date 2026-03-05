from __future__ import annotations

import json


def _parse_sse(raw: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    blocks = [b.strip() for b in raw.split("\n\n") if b.strip()]
    for block in blocks:
        event_name = "message"
        payload: dict = {}
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                text = line.split(":", 1)[1].strip()
                if text:
                    payload = json.loads(text)
        events.append((event_name, payload))
    return events


def test_v2_stream_emits_primary_then_done_with_consistent_options(client) -> None:
    create = client.post(
        "/v2/game/slots",
        json={"slot_name": "stream-order", "world_seed": "stream-order-seed", "canon_gen": 9},
    )
    assert create.status_code == 200
    slot_id = create.json()["slot_id"]

    with client.stream(
        "POST",
        f"/v2/game/slots/{slot_id}/turns",
        json={
            "text": "advance chapter and provide actions",
            "stream": True,
            "language": "zh",
            "client_turn_id": "test-client-turn-1",
        },
    ) as resp:
        assert resp.status_code == 200
        raw = "".join(resp.iter_text())

    events = _parse_sse(raw)
    event_names = [name for name, _ in events]
    assert "ack" in event_names
    assert "primary" in event_names
    assert "done" in event_names
    assert "options" not in event_names
    assert event_names.index("primary") < event_names.index("done")

    done_payload = next(payload for name, payload in events if name == "done")
    assert isinstance(done_payload.get("action_options"), list)
    assert done_payload.get("action_options")
    timings = done_payload.get("timings", {})
    assert int(timings.get("first_interactive_ms", 0)) >= 0
    assert int(timings.get("done_ms", 0)) >= int(timings.get("first_interactive_ms", 0))
