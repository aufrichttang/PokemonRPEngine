from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

from app.providers.xfyun_ws import build_ws_authorized_url


def test_ws_signature_url_generation() -> None:
    dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    url = build_ws_authorized_url(
        "wss://maas-api.cn-huabei-1.xf-yun.com/v1.1/chat",
        api_key="test_key",
        api_secret="test_secret",
        dt=dt,
    )

    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "wss"
    assert "authorization" in query
    assert "date" in query
    assert query.get("host", [""])[0] == "maas-api.cn-huabei-1.xf-yun.com"
