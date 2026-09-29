from conftest import headers, register


def test_register_login_and_me(client):
    http, _ = client
    auth = register(http, "YASH@EXAMPLE.COM")
    assert auth["user"]["email"] == "yash@example.com"
    assert auth["user"]["questions_left"] is None
    assert http.get("/auth/me", headers=headers(auth["token"])).json()["id"] == auth["user"]["id"]

    login = http.post("/auth/login", json={"email": "yash@example.com", "password": "password123"})
    assert login.status_code == 200
    assert login.json()["user"]["id"] == auth["user"]["id"]


def test_auth_errors_use_contract(client):
    http, _ = client
    register(http)
    duplicate = http.post("/auth/register", json={"name": "Yash", "email": "yash@example.com", "password": "password123"})
    assert duplicate.status_code == 422
    assert duplicate.json()["error"]["code"] == "validation_error"

    wrong = http.post("/auth/login", json={"email": "yash@example.com", "password": "wrong"})
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "unauthorized"
    assert http.get("/auth/me").json()["error"]["code"] == "unauthorized"


def test_registration_validates_input(client):
    http, _ = client
    response = http.post("/auth/register", json={"name": " ", "email": "bad-email", "password": "short"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"

