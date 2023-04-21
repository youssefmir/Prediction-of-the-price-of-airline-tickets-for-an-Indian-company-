"""Tests de l'export du modèle vers le navigateur (format JSON compact)."""

import shutil

import numpy as np
import pytest
from sklearn.ensemble import GradientBoostingRegressor

from flight_prices import modeling
from flight_prices.data import clean, economy_only, load_raw
from flight_prices.export import LEAF, export_model, predict_exported
from flight_prices.features import build_features
from flight_prices.parity import check_js


@pytest.fixture(scope="module")
def fitted():
    flights = economy_only(clean(load_raw())[0]).sample(1500, random_state=2)
    features = build_features(flights)
    model = modeling.on_log_price(
        GradientBoostingRegressor(n_estimators=40, max_depth=4, random_state=0)
    )
    model.fit(features, flights["price"])
    return model, flights, features


def test_export_structure(fitted):
    model, _, features = fitted
    exported = export_model(model)
    prep = model.regressor_.named_steps["prep"]
    assert len(exported["columns"]) == prep.transform(features.head(1)).shape[1]
    assert len(exported["trees"]) == 40
    for tree in exported["trees"]:
        assert len(tree["f"]) == len(tree["v"]) == len(tree["r"])
        leaves = [i for i, f in enumerate(tree["f"]) if f == LEAF]
        assert all(tree["r"][i] == 0 for i in leaves)


def test_exported_model_reproduces_sklearn(fitted):
    model, _, features = fitted
    sample = features.head(300)
    expected = model.predict(sample)
    assert np.abs(predict_exported(export_model(model), sample) - expected).max() < 0.01


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js n'est pas installé")
def test_browser_model_matches_python(fitted):
    model, flights, features = fitted
    rows = flights.head(250)
    result = check_js(export_model(model), rows, model.predict(features.loc[rows.index]))
    assert result["n"] == 250
    assert result["maxDiff"] < 0.01
