from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.models import SaveSlot, TimelineEvent


def test_chat_memory_pipeline_and_debug(client, db_session) -> None:
    create_resp = client.post(
        "/v2/game/slots",
        json={
            "slot_name": "pokemon test",
            "world_seed": "my-seed-001",
            "canon_gen": 9,
            "canon_game": "sv",
        },
    )
    assert create_resp.status_code == 200

    slot_payload = create_resp.json()
    slot_id = slot_payload["slot_id"]
    assert slot_payload["world_profile"]["seed"] == "my-seed-001"
    assert slot_payload["world_profile"].get("continent_name")
    assert slot_payload["world_profile"].get("theme_tags")

    first = client.post(
        f"/v2/game/slots/{slot_id}/turns",
        json={"text": "Investigate the first clue in town", "stream": False},
    )
    assert first.status_code == 200
    first_payload = first.json()
    assert isinstance(first_payload.get("action_options"), list)
    assert "narrative" in first_payload
    assert first_payload["narrative"].get("primary", "")

    slot_obj = db_session.query(SaveSlot).filter(SaveSlot.id == uuid.UUID(slot_id)).one()
    events = (
        db_session.execute(
            select(TimelineEvent).where(TimelineEvent.session_id == slot_obj.session_id)
        )
        .scalars()
        .all()
    )
    assert events

    lore = client.get(f"/v2/game/slots/{slot_id}/lore")
    time_resp = client.get(f"/v2/game/slots/{slot_id}/time")
    factions = client.get(f"/v2/game/slots/{slot_id}/factions")
    assert lore.status_code == 200
    assert time_resp.status_code == 200
    assert factions.status_code == 200

    reclassify = client.post(f"/v2/game/slots/{slot_id}/debug/reclassify-memories")
    assert reclassify.status_code == 200

    for i in range(2, 8):
        resp = client.post(
            f"/v2/game/slots/{slot_id}/turns",
            json={"text": f"Continue chapter progression round {i}", "stream": False},
        )
        assert resp.status_code == 200

    export_resp = client.get(f"/v2/game/slots/{slot_id}/export")
    assert export_resp.status_code == 200
    assert export_resp.text


def test_chat_stream_emits_done_with_action_options(client) -> None:
    create_resp = client.post(
        "/v2/game/slots",
        json={
            "slot_name": "stream test",
            "world_seed": "stream-seed-001",
            "canon_gen": 9,
            "canon_game": "sv",
        },
    )
    assert create_resp.status_code == 200
    slot_id = create_resp.json()["slot_id"]

    with client.stream(
        "POST",
        f"/v2/game/slots/{slot_id}/turns",
        json={"text": "Continue and provide actionable moves", "stream": True},
    ) as resp:
        assert resp.status_code == 200
        payload = "".join(resp.iter_text())

    assert "event: done" in payload
    assert '"action_options"' in payload
    assert '"narrative"' in payload
    assert "event: options" not in payload
