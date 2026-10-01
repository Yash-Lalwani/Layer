import asyncio
from types import SimpleNamespace

import pytest
from clerk_backend_api.models.emailaddress import VerificationStatus

from conftest import headers, register
from layer_api.auth.clerk import clerk_profile, verify_session
from layer_api.config import Settings
from layer_api.schemas import ApiError


def test_clerk_user_gets_layer_id_and_keeps_it(client):
    http, _ = client
    auth = register(http, "YASH@EXAMPLE.COM")
    user = auth["user"]
    assert user["email"] == "yash@example.com"
    assert user["questions_left"] is None
    assert http.get("/auth/me", headers=headers(auth["token"])).json()["id"] == user["id"]


def test_old_auth_routes_and_tokens_are_rejected(client):
    http, _ = client
    assert http.post("/auth/register", json={}).status_code == 404
    assert http.post("/auth/login", json={}).status_code == 404
    assert http.get("/auth/me").status_code == 401
    assert http.get("/auth/me", headers=headers("old-layer-jwt")).status_code == 401


def test_same_email_never_links_another_clerk_account(client):
    http, _ = client
    original = register(http)
    token = "different-clerk-session"
    http.app.state.test_identities[token] = ("different-clerk-user", "Yash", "yash@example.com")
    response = http.get("/auth/me", headers=headers(token))
    assert response.status_code == 409
    assert http.get("/auth/me", headers=headers(original["token"])).json()["id"] == original["user"]["id"]


def test_clerk_verification_restricts_token_type_and_origin(monkeypatch):
    captured = {}

    def fake_authenticate(request, options):
        captured["options"] = options
        return SimpleNamespace(is_signed_in=True, payload={"sub": "user_clerk_123"})

    monkeypatch.setattr("layer_api.auth.clerk.authenticate_request", fake_authenticate)
    settings = Settings(_env_file=None, oauth_state_secret="state", clerk_secret_key="secret", clerk_jwt_key="public", frontend_url="http://localhost:3000")
    assert verify_session(SimpleNamespace(), settings) == "user_clerk_123"
    assert captured["options"].accepts_token == ["session_token"]
    assert captured["options"].authorized_parties == ["http://localhost:3000"]


def test_clerk_verification_rejects_signed_out(monkeypatch):
    monkeypatch.setattr("layer_api.auth.clerk.authenticate_request", lambda request, options: SimpleNamespace(is_signed_in=False, payload=None))
    settings = Settings(_env_file=None, oauth_state_secret="state", clerk_secret_key="secret", clerk_jwt_key="public")
    with pytest.raises(ApiError) as error:
        verify_session(SimpleNamespace(), settings)
    assert error.value.status_code == 401


def test_only_verified_primary_clerk_email_can_create_layer_user(monkeypatch):
    email = SimpleNamespace(
        id="primary",
        email_address="Yash@Example.com",
        verification=SimpleNamespace(status=VerificationStatus.UNVERIFIED),
    )

    async def get_user(*, user_id):
        return SimpleNamespace(
            primary_email_address_id="primary",
            email_addresses=[email],
            first_name="Yash", last_name="Lalwani",
        )

    monkeypatch.setattr("layer_api.auth.clerk.Clerk", lambda **kwargs: SimpleNamespace(users=SimpleNamespace(get_async=get_user)))
    settings = Settings(_env_file=None, oauth_state_secret="state", clerk_secret_key="secret")
    with pytest.raises(ApiError) as error:
        asyncio.run(clerk_profile("user_clerk_123", settings))
    assert error.value.status_code == 403

    email.verification.status = VerificationStatus.VERIFIED
    assert asyncio.run(clerk_profile("user_clerk_123", settings)) == ("Yash Lalwani", "yash@example.com")
