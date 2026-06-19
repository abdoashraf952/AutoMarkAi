"""
tests/test_api.py — AutoMark AI CRM Agent (ORCAST)

FastAPI TestClient tests that don't require live services (no DB, no Gemini, no HubSpot).
These validate routing, request/response shapes, and webhook verification handshakes.

Run with:  pytest tests/test_api.py -v
"""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """Import app with lifespan patched to no-op so tests don't need DB or Gemini."""
    from contextlib import asynccontextmanager

    from main import app

    @asynccontextmanager
    async def _noop_lifespan(app):
        yield  # skip DB init, graph compile, etc.

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan
    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
    finally:
        app.router.lifespan_context = original_lifespan


# ─────────────────────────────────────────────────────────────────────────────
# Root + health endpoints
# ─────────────────────────────────────────────────────────────────────────────

class TestHealthEndpoints:

    def test_root_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["service"] == "AutoMark AI ORCAST CRM Agent"
        assert body["version"] == "3.0.0"
        assert body["status"] == "running"

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"


# ─────────────────────────────────────────────────────────────────────────────
# Messenger webhook — verification handshake (no DB needed)
# ─────────────────────────────────────────────────────────────────────────────

class TestMessengerWebhook:

    def _verify_url(self, token: str, challenge: str = "abc123"):
        return (
            f"/messenger/webhook"
            f"?hub.mode=subscribe"
            f"&hub.verify_token={token}"
            f"&hub.challenge={challenge}"
        )

    def test_valid_verify_token_echoes_challenge(self, client, monkeypatch):
        monkeypatch.setattr("app.api.messenger.settings.MESSENGER_VERIFY_TOKEN", "correct_token")
        resp = client.get(self._verify_url("correct_token", "test_challenge"))
        assert resp.status_code == 200
        assert resp.text == "test_challenge"

    def test_invalid_verify_token_returns_403(self, client, monkeypatch):
        monkeypatch.setattr("app.api.messenger.settings.MESSENGER_VERIFY_TOKEN", "correct_token")
        monkeypatch.setattr("app.api.messenger.settings.FB_COMMENTS_VERIFY_TOKEN", "correct_token")
        resp = client.get(self._verify_url("wrong_token"))
        assert resp.status_code == 403

    def test_post_empty_payload_returns_ok(self, client):
        resp = client.post("/messenger/webhook", json={"entry": []})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ─────────────────────────────────────────────────────────────────────────────
# Facebook Comments webhook — verification handshake
# ─────────────────────────────────────────────────────────────────────────────

class TestFacebookWebhook:

    def _verify_url(self, token: str, challenge: str = "fb_chal"):
        return (
            f"/facebook/webhook"
            f"?hub.mode=subscribe"
            f"&hub.verify_token={token}"
            f"&hub.challenge={challenge}"
        )

    def test_valid_verify_token_echoes_challenge(self, client, monkeypatch):
        monkeypatch.setattr("app.api.facebook_comments.settings.FB_COMMENTS_VERIFY_TOKEN", "fb_token")
        resp = client.get(self._verify_url("fb_token", "fb_chal_value"))
        assert resp.status_code == 200
        assert resp.text == "fb_chal_value"

    def test_invalid_verify_token_returns_403(self, client, monkeypatch):
        monkeypatch.setattr("app.api.facebook_comments.settings.FB_COMMENTS_VERIFY_TOKEN", "fb_token")
        resp = client.get(self._verify_url("bad_token"))
        assert resp.status_code == 403

    def test_post_empty_payload_returns_ok(self, client):
        resp = client.post("/facebook/webhook", json={"entry": []})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ─────────────────────────────────────────────────────────────────────────────
# Vapi webhook — assistant-request (no DB, no Gemini needed)
# ─────────────────────────────────────────────────────────────────────────────

class TestVapiWebhook:

    ASSISTANT_REQUEST = {
        "message": {
            "type": "assistant-request",
            "call": {
                "id": "call_123",
                "customer": {"number": "+1555000000"},
            },
        }
    }

    def _post(self, client, payload: dict, secret: str = ""):
        raw = json.dumps(payload).encode()
        headers = {}
        if secret:
            headers["x-vapi-secret"] = secret  # Vapi sends plain secret, not HMAC
        return client.post("/vapi/webhook", content=raw, headers={"Content-Type": "application/json", **headers})

    def test_assistant_request_returns_config(self, client, monkeypatch):
        monkeypatch.setattr("app.api.vapi.settings.VAPI_WEBHOOK_SECRET", "")
        resp = self._post(client, self.ASSISTANT_REQUEST)
        assert resp.status_code == 200
        body = resp.json()
        assert "assistant" in body
        assert "firstMessage" in body["assistant"]

    def test_end_of_call_returns_received(self, client, monkeypatch):
        monkeypatch.setattr("app.api.vapi.settings.VAPI_WEBHOOK_SECRET", "")
        payload = {"message": {"type": "end-of-call-report", "call": {"id": "c1", "duration": 30}}}
        resp = self._post(client, payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "received"

    def test_invalid_signature_returns_403(self, client, monkeypatch):
        monkeypatch.setattr("app.api.vapi.settings.VAPI_WEBHOOK_SECRET", "my_secret")
        raw = json.dumps(self.ASSISTANT_REQUEST).encode()
        resp = client.post(
            "/vapi/webhook",
            content=raw,
            headers={"Content-Type": "application/json", "x-vapi-secret": "wrong_secret"},
        )
        assert resp.status_code == 403

    def test_valid_signature_accepted(self, client, monkeypatch):
        monkeypatch.setattr("app.api.vapi.settings.VAPI_WEBHOOK_SECRET", "my_secret")
        resp = self._post(client, self.ASSISTANT_REQUEST, secret="my_secret")
        assert resp.status_code == 200

    def test_unknown_event_type_returns_ok(self, client, monkeypatch):
        monkeypatch.setattr("app.api.vapi.settings.VAPI_WEBHOOK_SECRET", "")
        payload = {"message": {"type": "status-update", "call": {"id": "c1", "customer": {}}}}
        resp = self._post(client, payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
