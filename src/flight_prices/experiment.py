"""Enchaînement complet de l'étude : données → modèles → évaluation (utilisé par le site)."""

from __future__ import annotations

from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import TransformedTargetRegressor

from . import modeling
from .config import CACHE_DIR
from .data import CleaningReport, clean, economy_only, load_raw
from .features import build_features, count_conflicts

CACHE_FILE = CACHE_DIR / "experiment.joblib"
FINAL_NAME = "Gradient boosting (réglé)"
TREES = ("Forêt aléatoire", FINAL_NAME)


@dataclass
class Experiment:
    """Résultats de l'étude, du nettoyage à l'évaluation finale."""

    tidy: pd.DataFrame
    report: CleaningReport
    flights: pd.DataFrame  # périmètre de modélisation (hors classe affaires)
    x_train: pd.DataFrame
    x_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series
    cv_table: pd.DataFrame
    search_table: pd.DataFrame
    best_params: dict
    test_table: pd.DataFrame
    final_model: TransformedTargetRegressor
    test_predictions: np.ndarray
    interval: tuple[float, float]
    importances: pd.DataFrame
    model_nodes: dict[str, int]
    conflicts: int


def run_experiment(use_cache: bool = False) -> Experiment:
    """Exécute toute l'étude (≈ 2 min) ou relit le dernier résultat mis en cache."""
    if use_cache and CACHE_FILE.exists():
        return joblib.load(CACHE_FILE)

    tidy, report = clean(load_raw())
    flights = economy_only(tidy)
    features = build_features(flights)
    x_train, x_test, y_train, y_test = modeling.split(features, flights["price"])

    candidates = modeling.candidate_models()
    cv_table = modeling.compare_models(candidates, x_train, y_train)
    search = modeling.tune_gradient_boosting(x_train, y_train)

    finalists = {name: m for name, m in candidates.items() if name != "Gradient boosting"}
    finalists[FINAL_NAME] = search.best_estimator_
    test_table, fitted = modeling.evaluate_on_test(finalists, x_train, y_train, x_test, y_test)
    final_model = fitted[FINAL_NAME]

    experiment = Experiment(
        tidy=tidy,
        report=report,
        flights=flights,
        x_train=x_train,
        x_test=x_test,
        y_train=y_train,
        y_test=y_test,
        cv_table=cv_table,
        search_table=modeling.search_results(search),
        best_params={
            k.removeprefix("regressor__model__"): v for k, v in search.best_params_.items()
        },
        test_table=test_table,
        final_model=final_model,
        test_predictions=final_model.predict(x_test),
        interval=modeling.ratio_interval(search.best_estimator_, x_train, y_train),
        importances=modeling.feature_importances(final_model, x_test, y_test),
        model_nodes={name: modeling.node_count(m) for name, m in fitted.items() if name in TREES},
        conflicts=count_conflicts(features, flights["price"]),
    )
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(experiment, CACHE_FILE)
    return experiment
