"""Tests de la construction des variables explicatives."""

import pandas as pd

from flight_prices.config import HUBS
from flight_prices.features import (
    FEATURES,
    build_features,
    clock_to_minutes,
    count_conflicts,
    group_info,
    layovers,
)


def flight(**overrides) -> pd.DataFrame:
    row = {
        "airline": "IndiGo",
        "cabin": "Economy",
        "source": "Bangalore",
        "destination": "Delhi",
        "route": "BLR → DEL",
        "journey_date": pd.Timestamp("2019-03-24"),
        "dep_time": "22:20",
        "duration_min": 170,
        "n_stops": 0,
        "additional_info": "No info",
        "price": 3897,
    }
    row.update(overrides)
    return pd.DataFrame([row])


def test_clock_to_minutes_ignores_date_suffix():
    assert clock_to_minutes("05:50") == 350
    assert clock_to_minutes("01:10 22 Mar") == 70


def test_layovers():
    assert layovers("CCU → IXR → BBI → BLR") == ["IXR", "BBI"]
    assert layovers("BLR → DEL") == []


def test_group_info_keeps_frequent_labels():
    assert group_info("No check-in baggage included") == "No check-in baggage included"
    assert group_info("Red-eye flight") == "Other"


def test_build_features_overnight_flight():
    x = build_features(flight()).iloc[0]
    assert list(build_features(flight()).columns) == FEATURES
    assert x["dep_minutes"] == 22 * 60 + 20
    assert x["arr_minutes"] == 70  # 22:20 + 2 h 50 = 01:10 le lendemain
    assert x["arr_day_offset"] == 1
    assert x["journey_weekday"] == 6  # dimanche
    assert x["journey_doy"] == 83
    assert all(x[f"via_{hub}"] == 0 for hub in HUBS)


def test_build_features_layover_flags():
    x = build_features(flight(route="DEL → LKO → BOM → COK", n_stops=2)).iloc[0]
    assert x["via_BOM"] == 1
    assert x["via_DEL"] == 0  # Delhi est le départ, pas une escale


def test_count_conflicts():
    features = pd.DataFrame({"a": [1, 1, 2, 2, 3]})
    prices = pd.Series([100, 120, 50, 50, 70])
    assert count_conflicts(features, prices) == 1
