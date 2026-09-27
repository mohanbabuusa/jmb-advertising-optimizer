from copy import deepcopy
from datetime import date

import pytest
from optimizer.adapters.local.seed import generate
from optimizer.domain.forecast import forecast, predict


def history():
    return generate(date(2026, 9, 19))["histories"]["wireless-headphones"]


def test_seed_reproducible_and_complete():
    seed = generate(date(2026, 9, 19))
    assert seed == generate(date(2026, 9, 19))
    assert len(seed["products"]) == 5
    assert sum(len(h["observations"]) for h in seed["histories"].values()) == 450


def test_known_constant_forecast_and_accuracy():
    data = history()
    for row in data["observations"]:
        row["units"] = 10
    result = forecast(data)
    assert [r["predictedUnits"] for r in result["horizon"]] == [10] * 7
    assert result["totalUnits"] == 70
    assert result["requiredInventoryUnits"] == 77
    assert result["confidenceScore"] == 1
    assert result["backtest"]["wape"] == 0


def test_backtest_has_no_future_leakage():
    data = history()
    for row in data["observations"]:
        row["units"] = 10
    for row in data["observations"][-7:]:
        row["units"] = 20
    result = forecast(data)
    assert result["backtest"]["wape"] == pytest.approx(70 / 350)
    assert result["confidenceScore"] == .8
    assert result["horizon"][0]["predictedUnits"] == 13  # 12.5 rounds half up


def test_zero_demand_confidence_unavailable():
    data = history()
    for row in data["observations"]:
        row["units"] = 0
    assert forecast(data)["confidenceScore"] is None


@pytest.mark.parametrize("fault", ["missing", "duplicate", "negative", "boolean"])
def test_invalid_history_rejected(fault):
    data = history()
    if fault == "missing": data["observations"].pop()
    if fault == "duplicate": data["observations"][1]["date"] = data["observations"][0]["date"]
    if fault == "negative": data["observations"][1]["units"] = -1
    if fault == "boolean": data["observations"][1]["units"] = True
    with pytest.raises(ValueError): forecast(data)


def test_forecast_does_not_mutate_input():
    data = history()
    before = deepcopy(data)
    forecast(data)
    assert data == before
