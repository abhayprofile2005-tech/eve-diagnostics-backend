import os

# Point the app at a throwaway SQLite file *before* app modules are
# imported, so app.database picks it up instead of the dev database.
os.environ["DATABASE_URL"] = "sqlite:///./test_eve_diagnostics.db"
os.environ["WEBHOOK_SHARED_SECRET"] = "test-webhook-secret"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_database():
    """Give every test a clean schema so tests never leak state into each other."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def api():
    return client


def signup_and_login(api, email="alice@example.com", password="supersecret1"):
    api.post("/auth/signup", json={"email": email, "password": password, "full_name": "Alice"})
    resp = api.post("/auth/login", data={"username": email, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def make_centre_and_test(api, headers, price=500.0):
    centre = api.post(
        "/centres/", json={"name": "City Diagnostics", "location": "Prayagraj"}, headers=headers
    ).json()
    test = api.post(
        f"/centres/{centre['id']}/tests/",
        json={"name": "Complete Blood Count", "price": price},
        headers=headers,
    ).json()
    return centre, test
