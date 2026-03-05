from __future__ import annotations

import uuid

from app.db.models import SaveSlot


def test_v2_slot_has_kernel_summaries(client) -> None:
    create = client.post(
        "/v2/game/slots",
        json={
            "slot_name": "kernel-save",
            "world_seed": "kernel-seed",
            "canon_gen": 9,
            "canon_game": "sv",
        },
    )
    assert create.status_code == 200
    payload = create.json()
    slot_id = payload["slot_id"]
    assert payload["schema_version"] == 3
    assert "lore_kernel_summary" in payload
    assert "time_kernel_summary" in payload
    assert "faction_kernel_summary" in payload

    lore = client.get(f"/v2/game/slots/{slot_id}/lore")
    time_resp = client.get(f"/v2/game/slots/{slot_id}/time")
    faction = client.get(f"/v2/game/slots/{slot_id}/factions")
    assert lore.status_code == 200
    assert time_resp.status_code == 200
    assert faction.status_code == 200
    assert lore.json()["lore_kernel"]["protocol_phase"]

    turn = client.post(
        f"/v2/game/slots/{slot_id}/turns",
        json={"text": "investigate faction conflict", "stream": False, "language": "zh"},
    )
    assert turn.status_code == 200
    turn_payload = turn.json()
    assert "kernel_delta_summary" in turn_payload
    assert "time_class_applied" in turn_payload


def test_v2_legacy_slot_blocked(client, db_session) -> None:
    create = client.post(
        "/v2/game/slots",
        json={"slot_name": "legacy-save", "world_seed": "legacy-seed", "canon_gen": 9},
    )
    assert create.status_code == 200
    slot_id = create.json()["slot_id"]
    slot = db_session.query(SaveSlot).filter(SaveSlot.id == uuid.UUID(slot_id)).one()
    slot.schema_version = 2
    db_session.add(slot)
    db_session.commit()

    blocked = client.get(f"/v2/game/slots/{slot_id}")
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "slot_upgrade_required"
