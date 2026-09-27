import pytest
from optimizer.domain.guardrails import validate, eligible


def checks(proposed=120000, current=100000, confidence=.8, inventory=110, approved=False):
    return validate({"weeklyBudgetCents": current, "inventory": {"availableUnits": inventory}},
                    {"confidenceScore": confidence, "requiredInventoryUnits": 110}, proposed, approved=approved)


def test_boundaries_pass_but_human_approval_pending():
    results = checks()
    assert eligible(results)
    assert results[-1]["status"] == "PENDING"
    assert all(r["status"] == "PASS" for r in checks(approved=True))


@pytest.mark.parametrize("kwargs,failed", [
    ({"proposed": 120001}, "budget_increase"),
    ({"proposed": 500001, "current": 450000}, "weekly_cap"),
    ({"confidence": .7999}, "confidence"),
    ({"confidence": None}, "confidence"),
    ({"inventory": 109}, "inventory"),
    ({"proposed": -1}, "weekly_cap"),
])
def test_unsafe_proposals_blocked(kwargs, failed):
    result = checks(**kwargs)
    assert not eligible(result)
    assert next(r for r in result if r["checkId"] == failed)["status"] == "FAIL"


def test_exact_weekly_cap_passes():
    assert eligible(checks(proposed=500000, current=450000))
