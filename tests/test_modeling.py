"""Tests des métriques et du pipeline de modélisation."""

import numpy as np
import pytest

from flight_prices import modeling
from flight_prices.data import clean, economy_only, load_raw
from flight_prices.features import build_features


def test_metrics_of_a_perfect_prediction():
    y = np.array([3000.0, 5000.0, 9000.0])
    metrics = modeling.regression_metrics(y, y)
    assert metrics["MAE"] == 0
    assert metrics["RMSE"] == 0
    assert metrics["R2"] == 1


def test_metrics_known_values():
    metrics = modeling.regression_metrics(np.array([100.0, 200.0]), np.array([110.0, 180.0]))
    assert metrics["MAE"] == pytest.approx(15)
    assert metrics["RMSE"] == pytest.approx(np.sqrt(250))
    assert metrics["MAPE"] == pytest.approx(0.1)


def test_final_params_belong_to_search_space():
    for name, value in modeling.FINAL_PARAMS.items():
        assert value in modeling.SEARCH_SPACE[f"regressor__model__{name}"]


@pytest.fixture(scope="module")
def sample():
    flights = economy_only(clean(load_raw())[0]).sample(800, random_state=0)
    return build_features(flights), flights["price"]


def test_split_is_80_20(sample):
    x, y = sample
    x_train, x_test, _, _ = modeling.split(x, y)
    assert len(x_train) == 640
    assert len(x_test) == 160


def test_final_model_learns_on_a_sample(sample):
    x, y = sample
    model = modeling.final_model().fit(x, y)
    predictions = model.predict(x)
    assert np.all(predictions > 0)
    assert modeling.regression_metrics(y, predictions)["R2"] > 0.9
    assert modeling.node_count(model) > 400
