from uuid import uuid4


def apply_approved_budget(state: dict, recommendation: dict, decision: dict, checks: list[dict], now: str) -> dict:
    """Private in-transaction mutation. The caller commits approval, action and audit together."""
    if decision["decision"] != "APPROVE" or decision["actorId"] != "local-demo-user":
        raise ValueError("Explicit local human approval is required.")
    if decision["proposalHash"] != recommendation["proposalHash"] or any(c["status"] != "PASS" for c in checks):
        raise ValueError("A matching proposal and passing execution checks are required.")
    rid = recommendation["recommendationId"]
    if rid in state["actions"]:
        raise ValueError("Recommendation already executed.")
    campaign = state["campaigns"][recommendation["productId"]]
    before = campaign["weeklyBudgetCents"]
    campaign["weeklyBudgetCents"] = recommendation["proposal"]["proposedWeeklyBudgetCents"]
    campaign["version"] += 1
    action = {"actionId": str(uuid4()), "recommendationId": rid, "campaignId": campaign["campaignId"],
              "beforeWeeklyBudgetCents": before, "afterWeeklyBudgetCents": campaign["weeklyBudgetCents"],
              "executedAt": now, "campaignVersion": campaign["version"], "simulation": True}
    state["actions"][rid] = action
    return action
