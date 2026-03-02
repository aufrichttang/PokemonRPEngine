from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.models import TimelineEvent, User, UserRole


def _auth_headers(
    client, email: str = "admin@test.com", password: str = "Password123!"
) -> dict[str, str]:
    client.post("/v1/auth/register", json={"email": email, "password": password})
    login = client.post("/v1/auth/login", json={"email": email, "password": password})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_chat_memory_pipeline_and_debug(client, db_session) -> None:
    headers = _auth_headers(client)

    user = db_session.execute(select(User).where(User.email == "admin@test.com")).scalar_one()
    user.role = UserRole.admin
    db_session.add(user)
    db_session.commit()

    sess_resp = client.post(
        "/v1/sessions",
        json={"title": "pokemon test", "canon_gen": 9, "canon_game": "sv"},
        headers=headers,
    )
    assert sess_resp.status_code == 200
    session_id = sess_resp.json()["id"]

    first = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"text": "我们在常磐市调查失踪案", "stream": False},
        headers=headers,
    )
    assert first.status_code == 200

    events = (
        db_session.execute(
            select(TimelineEvent).where(TimelineEvent.session_id == uuid.UUID(session_id))
        )
        .scalars()
        .all()
    )
    assert events

    event_id = str(events[0].id)
    confirm = client.post(
        f"/v1/sessions/{session_id}/memory/confirm",
        json={"event_id": event_id, "confirm": True, "note": "用户确认"},
        headers=headers,
    )
    assert confirm.status_code == 200

    for i in range(2, 11):
        resp = client.post(
            f"/v1/sessions/{session_id}/messages",
            json={"text": f"继续推进剧情第{i}轮", "stream": False},
            headers=headers,
        )
        assert resp.status_code == 200

    debug = client.get(f"/v1/sessions/{session_id}/memory/debug", headers=headers)
    assert debug.status_code == 200
    payload = debug.json()
    assert "prompt_injection" in payload
    assert "CANON_FACTS" in payload["prompt_injection"]

    timeline = client.get(
        f"/v1/sessions/{session_id}/timeline/events?canon_level=pending", headers=headers
    )
    assert timeline.status_code == 200
    assert "items" in timeline.json()

    metrics_summary = client.get("/v1/admin/metrics/summary", headers=headers)
    assert metrics_summary.status_code == 200
    assert "requests_total" in metrics_summary.json()

    canon_pokemon = client.get("/v1/canon/pokemon?generation=9", headers=headers)
    assert canon_pokemon.status_code == 200
    assert "items" in canon_pokemon.json()
