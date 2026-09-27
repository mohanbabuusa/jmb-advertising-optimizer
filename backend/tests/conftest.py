from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from optimizer.handlers.api import create_app


@pytest.fixture
def now():
    return [datetime(2026, 9, 20, 12, tzinfo=timezone.utc)]


@pytest.fixture
def app(tmp_path, now):
    return create_app(tmp_path / "state.json", lambda: now[0])


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


def request_key():
    return {"Idempotency-Key": str(uuid4())}


def generate_rec(client, product="wireless-headphones"):
    response = client.post(f"/v1/products/{product}/recommendations", json={}, headers=request_key())
    assert response.status_code == 201, response.text
    return response.json()


def decision_body(rec, decision="APPROVE"):
    return {"decision": decision, "expectedVersion": rec["version"], "proposalHash": rec["proposalHash"]}
