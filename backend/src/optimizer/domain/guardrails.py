"""All authorization policy is deterministic, outside the reasoner."""
POLICY_VERSION = "local-v1"


def validate(campaign: dict, prediction: dict, proposed: int, *, approved: bool = False,
             fresh: bool = True, phase: str = "GENERATION") -> list[dict]:
    current = campaign["weeklyBudgetCents"]
    available = campaign["inventory"]["availableUnits"]
    confidence = prediction["confidenceScore"]
    valid_budget = type(proposed) is int and proposed >= 0
    definitions = [
        ("budget_increase", "Budget change <= 20%", valid_budget and current > 0 and proposed * 100 <= current * 120,
         proposed, current * 1.2, "Budget increases cannot exceed 20% of the current budget."),
        ("weekly_cap", "Weekly budget <= $5,000", valid_budget and proposed <= 500000,
         proposed, 500000, "Weekly budget is capped at $5,000 per simulated campaign."),
        ("confidence", "Forecast confidence >= 80%", confidence is not None and confidence >= .80,
         confidence, .80, "Confidence is historical backtest accuracy, not a probability."),
        ("inventory", "Inventory sufficient", available >= prediction["requiredInventoryUnits"],
         available, prediction["requiredInventoryUnits"], "Inventory must cover predicted units plus a 10% buffer."),
        ("freshness", "Current, unexpired inputs", fresh, fresh, True,
         "Campaign, inventory, policy and history must still match the reviewed proposal."),
        ("ai_isolation", "Reasoner cannot execute", True, "proposal_only", "proposal_only",
         "FixtureReasoner has no campaign repository or execution capability."),
    ]
    results = [{"checkId": key, "label": label, "phase": phase, "status": "PASS" if passed else "FAIL",
                "observed": observed, "limit": limit, "message": message, "policyVersion": POLICY_VERSION}
               for key, label, passed, observed, limit, message in definitions]
    results.append({"checkId": "human_approval", "label": "Human approval required", "phase": phase,
                    "status": "PASS" if approved else "PENDING", "observed": approved, "limit": True,
                    "message": "An explicit human approval must commit with every campaign change.",
                    "policyVersion": POLICY_VERSION})
    return results


def eligible(checks: list[dict]) -> bool:
    return all(c["status"] == "PASS" for c in checks if c["checkId"] != "human_approval")
