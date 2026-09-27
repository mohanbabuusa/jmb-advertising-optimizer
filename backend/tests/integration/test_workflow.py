from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from optimizer.application.service import AppError, Optimizer
from optimizer.adapters.local.store import JsonStore
from conftest import generate_rec, decision_body, request_key


def test_approval_changes_mock_budget_and_audits(client, app):
    rec = generate_rec(client)
    assert rec["status"] == "AWAITING_APPROVAL"
    before = client.get('/v1/products/wireless-headphones/campaign').json()
    response = client.post(f'/v1/recommendations/{rec["recommendationId"]}/decision',
                           json=decision_body(rec), headers=request_key())
    assert response.status_code == 200
    assert response.json()["status"] == "EXECUTED"
    after = client.get('/v1/products/wireless-headphones/campaign').json()
    assert before["weeklyBudgetCents"] == 100000
    assert after["weeklyBudgetCents"] == 115000
    assert after["metrics"] == before["metrics"]
    state = app.state.service.store.read()
    events = [r["eventType"] for r in state["audit"]]
    assert all(e in events for e in ['RECOMMENDATION_GENERATED', 'VALIDATION_COMPLETED', 'DECISION_RECORDED', 'EXECUTION_VALIDATED', 'CAMPAIGN_UPDATED'])
    assert len(state["actions"]) == len(state["decisions"]) == 1


def test_rejection_never_changes_campaign(client, app):
    rec = generate_rec(client)
    before = app.state.service.store.read()["campaigns"]
    result = client.post(f'/v1/recommendations/{rec["recommendationId"]}/decision',
                         json=decision_body(rec, 'REJECT'), headers=request_key()).json()
    assert result['status'] == 'REJECTED'
    assert app.state.service.store.read()["campaigns"] == before
    assert app.state.service.store.read()["actions"] == {}


def test_duplicate_approval_returns_receipt_once(client, app):
    rec, headers = generate_rec(client), request_key()
    url = f'/v1/recommendations/{rec["recommendationId"]}/decision'
    first = client.post(url, json=decision_body(rec), headers=headers)
    second = client.post(url, json=decision_body(rec), headers=headers)
    assert first.json() == second.json()
    assert client.post(url, json=decision_body(rec), headers=request_key()).status_code == 409
    assert len(app.state.service.store.read()["actions"]) == 1
    assert sum(a["eventType"] == "CAMPAIGN_UPDATED" for a in app.state.service.store.read()["audit"]) == 1


@pytest.mark.parametrize('product,check', [('smart-tv', 'weekly_cap'), ('bluetooth-speaker', 'inventory')])
def test_blocked_recommendation_cannot_execute(client, app, product, check):
    rec = generate_rec(client, product)
    assert rec['status'] == 'BLOCKED'
    assert next(c for c in rec['generationChecks'] if c['checkId'] == check)['status'] == 'FAIL'
    before = app.state.service.store.read()["campaigns"]
    result = client.post(f'/v1/recommendations/{rec["recommendationId"]}/decision',
                         json=decision_body(rec), headers=request_key())
    assert result.json()['status'] == 'BLOCKED'
    assert app.state.service.store.read()["campaigns"] == before


def test_expired_recommendation_cannot_execute(client, app, now):
    rec = generate_rec(client)
    now[0] += timedelta(minutes=31)
    assert client.get(f'/v1/recommendations/{rec["recommendationId"]}').json()['status'] == 'EXPIRED'
    result = client.post(f'/v1/recommendations/{rec["recommendationId"]}/decision', json=decision_body(rec), headers=request_key())
    assert result.json()['status'] == 'EXPIRED'
    assert not app.state.service.store.read()['actions']


def test_stale_approval_after_another_campaign_update(client, app):
    older, newer = generate_rec(client), generate_rec(client)
    client.post(f'/v1/recommendations/{newer["recommendationId"]}/decision', json=decision_body(newer), headers=request_key())
    result = client.post(f'/v1/recommendations/{older["recommendationId"]}/decision', json=decision_body(older), headers=request_key())
    assert result.json()['status'] == 'STALE'
    assert len(app.state.service.store.read()['actions']) == 1


def test_tampered_hash_and_extra_budget_rejected(client):
    rec = generate_rec(client)
    body = decision_body(rec)
    body['proposalHash'] = 'sha256:' + '0' * 64
    url = f'/v1/recommendations/{rec["recommendationId"]}/decision'
    assert client.post(url, json=body, headers=request_key()).status_code == 409
    body = {**decision_body(rec), 'proposedWeeklyBudgetCents': 1}
    assert client.post(url, json=body, headers=request_key()).status_code == 422


def test_same_key_different_decision_conflicts(client):
    rec, headers = generate_rec(client), request_key()
    url = f'/v1/recommendations/{rec["recommendationId"]}/decision'
    client.post(url, json=decision_body(rec, 'REJECT'), headers=headers)
    assert client.post(url, json=decision_body(rec), headers=headers).status_code == 409


def test_concurrent_approval_only_one_commit(client, app):
    rec = generate_rec(client)
    service = app.state.service
    def decide(_):
        try: return service.decide(rec['recommendationId'], decision_body(rec), str(uuid4()))['status']
        except AppError as e: return e.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(decide, range(2)))
    assert sorted(outcomes) == ['DECISION_CONFLICT', 'EXECUTED']
    assert len(service.store.read()['actions']) == 1


def test_failed_disk_commit_leaves_no_action_or_decision(client, app, monkeypatch):
    rec = generate_rec(client)
    service = app.state.service
    before = service.store.read()
    def broken_write(_): raise OSError('disk unavailable')
    monkeypatch.setattr(service.store, '_write', broken_write)
    with pytest.raises(OSError): service.decide(rec['recommendationId'], decision_body(rec), str(uuid4()))
    assert service.store.read() == before


def test_existing_audit_cannot_be_changed(app):
    store = app.state.service.store
    with pytest.raises(ValueError, match='immutable'):
        with store.transaction() as state:
            state['audit'][0]['eventType'] = 'tampered'
    assert store.read()['audit'][0]['eventType'] == 'SIMULATION_INITIALIZED'


def test_file_persistence_and_idempotency_after_restart(client, app):
    headers = request_key()
    first = client.post('/v1/products/wireless-headphones/recommendations', json={}, headers=headers).json()
    service = app.state.service
    restarted = Optimizer(JsonStore(service.store.path), service.reasoner, service.clock)
    assert restarted.generate('wireless-headphones', headers['Idempotency-Key']) == first


def test_untrusted_reasoner_output_fails_closed(app):
    class InvalidReasoner:
        def recommend(self, context):
            context['campaign']['weeklyBudgetCents'] = 999999
            return {'action': 'EXECUTE', 'proposedWeeklyBudgetCents': 1, 'reasoning': 'bypass', 'assumptions': []}
    service = app.state.service
    service.reasoner = InvalidReasoner()
    rec = service.generate('wireless-headphones', str(uuid4()))
    assert rec['status'] == 'FAILED'
    assert service.store.read()['campaigns']['wireless-headphones']['weeklyBudgetCents'] == 100000
    assert service.store.read()['audit'][-1]['eventType'] == 'RECOMMENDATION_FAILED'


def test_audit_pagination_and_invalid_origin(client):
    generate_rec(client)
    first = client.get('/v1/audit?productId=wireless-headphones&limit=2').json()
    second = client.get('/v1/audit', params={'productId': 'wireless-headphones', 'limit': 2, 'before': first['nextCursor']}).json()
    assert not set(a['eventId'] for a in first['items']) & set(a['eventId'] for a in second['items'])
    assert client.post('/v1/products/wireless-headphones/recommendations', json={},
                       headers={**request_key(), 'Origin': 'https://untrusted.example'}).status_code == 403
