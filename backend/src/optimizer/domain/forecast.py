"""Transparent weekday-average forecasting, with no model or network calls."""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from math import ceil

ALGORITHM_VERSION = "weekday-mean-v1"


def predict(observations: list[dict], days: int = 7) -> list[dict]:
    end = date.fromisoformat(observations[-1]["date"])
    result = []
    for offset in range(1, days + 1):
        day = end + timedelta(days=offset)
        values = [r["units"] for r in observations
                  if date.fromisoformat(r["date"]).weekday() == day.weekday()][-4:]
        if len(values) != 4:
            raise ValueError("Four observations per weekday are required.")
        units = int((Decimal(sum(values)) / 4).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        result.append({"date": day.isoformat(), "predictedUnits": units})
    return result


def forecast(history: dict) -> dict:
    rows = history["observations"]
    if len(rows) != 90:
        raise ValueError("Exactly 90 daily observations are required.")
    dates = [date.fromisoformat(r["date"]) for r in rows]
    if any(type(r["units"]) is not int or r["units"] < 0 for r in rows):
        raise ValueError("Demand must be nonnegative integer units.")
    if any(b - a != timedelta(days=1) for a, b in zip(dates, dates[1:])):
        raise ValueError("History must have consecutive, unique, ascending dates.")
    absolute_error = actual_total = 0
    for start in (62, 69, 76, 83):
        predictions = predict(rows[:start])
        for actual, prediction in zip(rows[start:start + 7], predictions):
            absolute_error += abs(actual["units"] - prediction["predictedUnits"])
            actual_total += actual["units"]
    score = max(0.0, 1 - absolute_error / actual_total) if actual_total else None
    horizon = predict(rows)
    total = sum(r["predictedUnits"] for r in horizon)
    previous = sum(r["units"] for r in rows[-7:])
    return {
        "productId": history["productId"], "datasetVersion": history["datasetVersion"],
        "algorithmVersion": ALGORITHM_VERSION, "horizon": horizon, "totalUnits": total,
        "requiredInventoryUnits": ceil(Decimal(total) * Decimal("1.10")),
        "confidenceScore": score, "confidenceMeaning": "backtest_accuracy_proxy",
        "backtest": {"holdoutDays": 28, "wape": absolute_error / actual_total if actual_total else None},
        "previousWeekUnits": previous, "demandChangePercent": (total / previous - 1) * 100 if previous else None,
        "simulation": True,
    }
