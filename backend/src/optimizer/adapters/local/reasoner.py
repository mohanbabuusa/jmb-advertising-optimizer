class FixtureReasoner:
    """Deterministic proposal generator; intentionally has no storage or API handle."""

    def recommend(self, context: dict) -> dict:
        campaign, prediction = context["campaign"], context["forecast"]
        increasing = (prediction["demandChangePercent"] or 0) > 0
        budget = campaign["weeklyBudgetCents"]
        proposed = (budget * 115 + 50) // 100 if increasing else budget
        enough = campaign["inventory"]["availableUnits"] >= prediction["requiredInventoryUnits"]
        reason = ("Forecast demand is increasing" if increasing else "Forecast demand is stable or declining")
        reason += (" while sufficient inventory is available." if enough else
                   ", but inventory is below the required buffer. The inventory guardrail must block this change.")
        return {
            "action": "SET_WEEKLY_BUDGET", "proposedWeeklyBudgetCents": proposed,
            "reasoning": reason + (" A measured 15% budget increase is proposed for human review." if increasing
                                    else " Maintain the current weekly budget for human review."),
            "assumptions": ["Synthetic data only; no real advertising provider.",
                            "Budget uplift is a fixed demo rule, not a causal sales prediction."],
        }
