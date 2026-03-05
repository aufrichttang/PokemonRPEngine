from __future__ import annotations

import uuid

from app.db.models import SaveSlot


def test_v2_slot_turn_and_action(client, db_session) -> None:
    create = client.post(
        "/v2/game/slots",
        json={
            "slot_name": "v2-save",
            "world_seed": "v2-seed-001",
            "canon_gen": 9,
            "canon_game": "sv",
            "player_profile": {"name": "hero", "gender": "male"},
        },
    )
    assert create.status_code == 200
    payload = create.json()
    slot_id = payload["slot_id"]
    assert payload["slot_name"] == "v2-save"
    assert payload["world_profile"]["seed"] == "v2-seed-001"
    assert "map_data" not in payload

    slots = client.get("/v2/game/slots")
    assert slots.status_code == 200
    assert slots.json()["items"]

    slot_detail = client.get(f"/v2/game/slots/{slot_id}")
    assert slot_detail.status_code == 200
    assert slot_detail.json()["turns"]
    assert "map_data" not in slot_detail.json()

    turn = client.post(
        f"/v2/game/slots/{slot_id}/turns",
        json={"text": "advance the main story", "stream": False, "language": "zh"},
    )
    assert turn.status_code == 200
    turn_payload = turn.json()
    assert turn_payload["narrative"]["primary"]
    assert isinstance(turn_payload["action_options"], list)

    action_options = turn_payload["action_options"]
    if action_options:
        action_id = action_options[0]["id"]
        action_resp = client.post(
            f"/v2/game/slots/{slot_id}/actions/{action_id}",
            json={"stream": False, "language": "zh"},
        )
        assert action_resp.status_code == 200
        assert action_resp.json()["narrative"]["primary"]

    with client.stream(
        "POST",
        f"/v2/game/slots/{slot_id}/turns",
        json={"text": "continue in stream", "stream": True, "language": "zh"},
    ) as resp:
        assert resp.status_code == 200
        stream_payload = "".join(resp.iter_text())
    assert "event: done" in stream_payload
    assert '"state_snapshot"' in stream_payload

    map_resp = client.get(f"/v2/game/slots/{slot_id}/map")
    assert map_resp.status_code == 404

    slot_obj = db_session.query(SaveSlot).filter(SaveSlot.id == uuid.UUID(slot_id)).one_or_none()
    assert slot_obj is not None
