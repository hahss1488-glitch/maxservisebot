import scripts.update_max_webhook as script


class DummyResponse:
    def __init__(self, status_code=200, payload=None, text="ok"):
        self.status_code = status_code
        self._payload = payload if payload is not None else []
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise script.requests.HTTPError(f"status={self.status_code}")


def test_resolve_webhook_url_from_full(monkeypatch):
    monkeypatch.setenv("MAX_WEBHOOK_URL", "https://example.com/max/webhook")
    assert script.resolve_webhook_url() == "https://example.com/max/webhook"


def test_resolve_webhook_url_from_base(monkeypatch):
    monkeypatch.delenv("MAX_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("WEBHOOK_URL", raising=False)
    monkeypatch.setenv("MAX_TUNNEL_URL", "https://abc.tunnel.dev/")
    assert script.resolve_webhook_url() == "https://abc.tunnel.dev/max/webhook"


def test_resolve_webhook_url_from_current_tunnel_file(monkeypatch, tmp_path):
    tunnel_file = tmp_path / "current_tunnel_url.txt"
    tunnel_file.write_text("https://from-file.tunnel.dev\n", encoding="utf-8")

    monkeypatch.delenv("MAX_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("WEBHOOK_URL", raising=False)
    monkeypatch.delenv("MAX_TUNNEL_URL", raising=False)
    monkeypatch.delenv("TUNNEL_URL", raising=False)
    monkeypatch.delenv("WEBHOOK_BASE_URL", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("CURRENT_TUNNEL_URL_FILE", str(tunnel_file))

    assert script.resolve_webhook_url() == "https://from-file.tunnel.dev/max/webhook"


def test_main_deletes_all_and_creates_one(monkeypatch):
    calls = {"delete_urls": [], "create_payload": None}

    monkeypatch.setenv("MAX_BOT_TOKEN", "token")
    monkeypatch.setenv("MAX_WEBHOOK_URL", "https://new.example/max/webhook")
    monkeypatch.setenv("MAX_API_BASE", "https://platform-api.max.ru")
    monkeypatch.setenv("MAX_WEBHOOK_SECRET", "secret-x")

    def fake_get(url, headers, timeout):
        assert url.endswith("/subscriptions")
        return DummyResponse(payload=[{"url": "https://old1/max/webhook"}, {"url": "https://old2/max/webhook"}])

    def fake_delete(url, headers, params, timeout):
        calls["delete_urls"].append(params["url"])
        return DummyResponse(status_code=200)

    def fake_post(url, headers, json, timeout):
        calls["create_payload"] = json
        return DummyResponse(status_code=200)

    monkeypatch.setattr(script.requests, "get", fake_get)
    monkeypatch.setattr(script.requests, "delete", fake_delete)
    monkeypatch.setattr(script.requests, "post", fake_post)

    assert script.main() == 0
    assert calls["delete_urls"] == ["https://old1/max/webhook", "https://old2/max/webhook"]
    assert calls["create_payload"] == {"url": "https://new.example/max/webhook", "secret": "secret-x"}


def test_main_continues_when_delete_fails(monkeypatch):
    calls = {"created": 0}

    monkeypatch.setenv("MAX_BOT_TOKEN", "token")
    monkeypatch.setenv("MAX_WEBHOOK_URL", "https://new.example/max/webhook")

    def fake_get(url, headers, timeout):
        return DummyResponse(payload=[{"url": "https://old1/max/webhook"}])

    def fake_delete(url, headers, params, timeout):
        return DummyResponse(status_code=500, text="fail")

    def fake_post(url, headers, json, timeout):
        calls["created"] += 1
        return DummyResponse(status_code=200)

    monkeypatch.setattr(script.requests, "get", fake_get)
    monkeypatch.setattr(script.requests, "delete", fake_delete)
    monkeypatch.setattr(script.requests, "post", fake_post)

    assert script.main() == 0
    assert calls["created"] == 1


def test_main_deletes_nested_subscription_urls(monkeypatch):
    calls = {"deleted": []}

    monkeypatch.setenv("MAX_BOT_TOKEN", "token")
    monkeypatch.setenv("MAX_WEBHOOK_URL", "https://new.example/max/webhook")

    def fake_get(url, headers, timeout):
        return DummyResponse(payload={"subscriptions": [{"subscription": {"url": "https://old-nested/max/webhook"}}]})

    def fake_delete(url, headers, params, timeout):
        calls["deleted"].append(params["url"])
        return DummyResponse(status_code=200)

    def fake_post(url, headers, json, timeout):
        return DummyResponse(status_code=200)

    monkeypatch.setattr(script.requests, "get", fake_get)
    monkeypatch.setattr(script.requests, "delete", fake_delete)
    monkeypatch.setattr(script.requests, "post", fake_post)

    assert script.main() == 0
    assert calls["deleted"] == ["https://old-nested/max/webhook"]
