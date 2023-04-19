"""Tests de l'API de prédiction d'un vol."""

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor

from flight_prices import modeling
from flight_prices.data import clean, economy_only, load_raw
from flight_prices.features import build_features
from flight_prices.predict import Flight, predict_price, to_table

FLIGHT = Flight("Jet Airways", "Delhi", "Cochin", "DEL → BOM → COK", "2019-05-24", "09:25", 1140)


def test_to_table_counts_stops():
    table = to_table([FLIGHT])
    assert table.loc[0, "n_stops"] == 1
    assert str(table.loc[0, "journey_date"].date()) == "2019-05-24"


def test_predict_price_returns_a_plausible_fare():
    flights = economy_only(clean(load_raw())[0]).sample(1500, random_state=1)
    model = modeling.on_log_price(GradientBoostingRegressor(n_estimators=60, random_state=0))
    model.fit(build_features(flights), flights["price"])
    price = predict_price(model, FLIGHT)
    assert np.isfinite(price)
    assert 2_000 < price < 30_000
