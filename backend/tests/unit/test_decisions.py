from uuid import uuid4

import pytest
from optimizer.application.service import AppError


def decide(service, rec, decision="APPROVE", key=None):
    return service.decide(rec["recommendationId"], {"decision": decision,
        "expectedVersion": rec["version"], "proposalHash": rec["proposalHash"]}, key or str(uuid4()))


def test_application_approval_without_http(app):
    service = app.state.service
    rec = service.generate("wireless-headphones", str(uuid4()))
    assert decide(service, rec)["status"] == "EXECUTED"
    assert service.store.read()["campaigns"]["wireless-headphones"]["weeklyBudgetCents"] == 115000


def test_application_rejection_without_http(app):
    service = app.state.service
    rec = service.generate("wireless-headphones", str(uuid4()))
    assert decide(service, rec, "REJECT")["status"] == "REJECTED"
    assert not service.store.read()["actions"]


def test_application_duplicate_decision_without_http(app):
    service, key = app.state.service, str(uuid4())
    rec = service.generate("wireless-headphones", str(uuid4()))
    first = decide(service, rec, key=key)
    assert decide(service, rec, key=key) == first
    with pytest.raises(AppError): decide(service, rec)
    assert len(service.store.read()["actions"]) == 1


def test_application_blocked_without_http(app):
    service = app.state.service
    rec = service.generate("smart-tv", str(uuid4()))
    assert decide(service, rec)["status"] == "BLOCKED"
    assert not service.store.read()["actions"]
