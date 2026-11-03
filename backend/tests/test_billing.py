import hashlib
import hmac
import json
import time
from datetime import timedelta
from types import SimpleNamespace

from conftest import headers, register
from test_demo import SimpleGraph, seed_template
from layer_api.api import billing

SECRET = "whsec_test"


def send_event(http, event_type: str, data: dict, secret: str = SECRET):
    http.app.state.settings.stripe_webhook_secret = SECRET
    payload = json.dumps({"type": event_type, "data": {"object": data}})
    stamp = int(time.time())
    signature = hmac.new(secret.encode(), f"{stamp}.{payload}".encode(), hashlib.sha256).hexdigest()
    return http.post("/billing/webhook", content=payload,
                     headers={"Stripe-Signature": f"t={stamp},v1={signature}", "Content-Type": "application/json"})


def me(http, token):
    return http.get("/auth/me", headers=headers(token)).json()


def test_webhook_rejects_bad_or_missing_signature(client):
    http, _ = client
    auth = register(http)
    forged = send_event(http, "checkout.session.completed", {"client_reference_id": auth["user"]["id"], "customer": "cus_1"},
                        secret="whsec_wrong")
    assert forged.status_code == 400 and forged.json()["error"]["code"] == "validation_error"
    unsigned = http.post("/billing/webhook", content=json.dumps({"type": "checkout.session.completed"}))
    assert unsigned.status_code == 400
    assert me(http, auth["token"])["plan"] == "free"


def test_checkout_and_subscription_events_change_the_plan(client):
    http, _ = client
    auth = register(http)
    completed = send_event(http, "checkout.session.completed", {"client_reference_id": auth["user"]["id"], "customer": "cus_1"})
    assert completed.status_code == 200
    assert me(http, auth["token"])["plan"] == "pro" and me(http, auth["token"])["questions_left"] == 50
    send_event(http, "customer.subscription.updated", {"customer": "cus_1", "status": "past_due"})
    assert me(http, auth["token"])["plan"] == "free"
    send_event(http, "customer.subscription.updated", {"customer": "cus_1", "status": "active"})
    assert me(http, auth["token"])["plan"] == "pro"
    send_event(http, "customer.subscription.deleted", {"customer": "cus_1", "status": "canceled"})
    assert me(http, auth["token"])["plan"] == "free"


def test_free_user_gets_ten_questions_a_day(client, monkeypatch):
    http, _ = client
    auth = register(http)
    bearer = headers(auth["token"])
    project = http.post("/projects", json={"name": "Phoenix"}, headers=bearer).json()["id"]
    chat_id = http.post(f"/projects/{project}/chats", json={}, headers=bearer).json()["id"]
    http.app.state.agent_graph = SimpleGraph()
    for _ in range(10):
        response = http.post(f"/chats/{chat_id}/messages/stream", json={"content": "Status?"}, headers=bearer)
        assert response.status_code == 200 and "event: final" in response.text
    assert '"questions_left": 0' in response.text
    blocked = http.post(f"/chats/{chat_id}/messages/stream", json={"content": "Status?"}, headers=bearer)
    assert blocked.status_code == 429 and blocked.json()["error"]["code"] == "daily_limit_reached"
    assert "Upgrade to Pro" in blocked.json()["error"]["message"]
    http.delete(f"/chats/{chat_id}", headers=bearer)
    assert me(http, auth["token"])["questions_left"] == 0
    tomorrow = billing.today() + timedelta(days=1)
    monkeypatch.setattr(billing, "today", lambda: tomorrow)
    assert me(http, auth["token"])["questions_left"] == 10
    chat_id = http.post(f"/projects/{project}/chats", json={}, headers=bearer).json()["id"]
    assert http.post(f"/chats/{chat_id}/messages/stream", json={"content": "Status?"}, headers=bearer).status_code == 200


def test_checkout_sends_the_user_to_stripe(client, monkeypatch):
    http, _ = client
    auth = register(http)
    bearer = headers(auth["token"])
    assert http.post("/billing/checkout", headers=bearer).json()["error"]["message"] == "Billing is not configured"
    calls = []

    async def create_async(params):
        calls.append(params)
        return SimpleNamespace(url="https://checkout.stripe.test/session")

    fake = SimpleNamespace(v1=SimpleNamespace(checkout=SimpleNamespace(sessions=SimpleNamespace(create_async=create_async))))
    monkeypatch.setattr(billing, "stripe_client", lambda settings: fake)
    response = http.post("/billing/checkout", headers=bearer)
    assert response.json() == {"url": "https://checkout.stripe.test/session"}
    assert calls[0]["mode"] == "subscription" and calls[0]["client_reference_id"] == auth["user"]["id"]
    assert calls[0]["customer_email"] == "yash@example.com"
    assert calls[0]["success_url"].endswith("/workspace?billing=success")
    assert http.post("/billing/portal", headers=bearer).status_code == 409


def test_guest_cannot_use_billing(client):
    http, engine = client
    seed_template(http)
    engine.collections["layer-demo-phoenix"] = "Phoenix Demo"
    guest = headers(http.post("/auth/demo").json()["token"])
    assert http.post("/billing/checkout", headers=guest).status_code == 403
    assert http.post("/billing/portal", headers=guest).status_code == 403
    assert http.get("/auth/me", headers=guest).json()["plan"] is None
