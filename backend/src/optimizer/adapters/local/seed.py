"""Reproducible data: fixed seeds, explicit end date, no external data sources."""
from datetime import date, timedelta
import random

PRODUCTS = [
    ("wireless-headphones", "Wireless Headphones", 85, 100000, 1500),
    ("smart-tv", "Smart TV", 20, 450000, 500),
    ("streaming-device", "Streaming Device", 50, 60000, 900),
    ("gaming-controller", "Gaming Controller", 65, 80000, 1100),
    ("bluetooth-speaker", "Bluetooth Speaker", 45, 70000, 100),
]


def generate(end: date) -> dict:
    products, histories, campaigns = [], {}, {}
    version = f"synthetic-v1-{end.isoformat()}"
    for index, (pid, name, base, budget, inventory) in enumerate(PRODUCTS):
        rng = random.Random(104729 + index)
        products.append({"productId": pid, "name": name, "description": "Synthetic consumer electronics product",
                         "currency": "USD", "simulation": True,
                         "demoNote": "Weekly cap scenario" if index == 1 else
                         "Low inventory scenario" if index == 4 else "Approval-ready scenario"})
        rows = []
        for offset in range(90):
            day = end - timedelta(days=89 - offset)
            seasonality = [1, 1.04, 1.02, 1.08, 1.14, 1.25, 1.18][day.weekday()]
            # A recent quiet week makes the transparent weekday baseline predict recovery.
            recent = .78 if offset >= 83 else 1
            units = max(0, round(base * seasonality * (1 + offset * .0004) * recent + rng.randint(-3, 3)))
            rows.append({"date": day.isoformat(), "units": units})
        histories[pid] = {"productId": pid, "datasetVersion": version, "startDate": rows[0]["date"],
                          "endDate": end.isoformat(), "observations": rows, "simulation": True}
        spend = budget * 72 // 100
        campaigns[pid] = {"campaignId": f"mock-{pid}", "productId": pid, "weeklyBudgetCents": budget,
                          "currency": "USD", "version": 1, "simulation": True,
                          "inventory": {"availableUnits": inventory, "version": 1},
                          "metrics": {"windowStart": (end - timedelta(days=6)).isoformat(),
                                      "windowEnd": end.isoformat(), "spendCents": spend,
                                      "impressions": 48000 + index * 7100, "clicks": 2160 + index * 190,
                                      "conversions": 108 + index * 13, "revenueCents": spend * 4}}
    return {"schemaVersion": 1, "manifest": {"version": version, "endDate": end.isoformat(),
            "generatorVersion": "synthetic-v1", "seed": 104729}, "products": products,
            "histories": histories, "campaigns": campaigns, "recommendations": {},
            "decisions": {}, "actions": {}, "idempotency": {}, "audit": []}
