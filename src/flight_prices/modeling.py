"""Modèles de prédiction du prix : préparation, comparaison, réglage et évaluation.

Protocole : un seul découpage entraînement / test (80 / 20). Toute sélection (choix du modèle,
hyperparamètres) se fait par validation croisée à 5 plis sur l'entraînement ; le jeu de test n'est
utilisé qu'une fois, pour l'évaluation finale.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
from sklearn.base import RegressorMixin, clone
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import (
    KFold,
    RandomizedSearchCV,
    cross_val_predict,
    cross_validate,
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeRegressor

from .config import CV_FOLDS, RANDOM_STATE, TEST_SIZE
from .features import CATEGORICAL_FEATURES, NUMERIC_FEATURES

SCORING = {
    "MAE": "neg_mean_absolute_error",
    "RMSE": "neg_root_mean_squared_error",
    "MAPE": "neg_mean_absolute_percentage_error",
    "R2": "r2",
}

# Espace de recherche du gradient boosting, borné pour que le modèle reste exportable
# vers le navigateur (≤ 400 arbres de profondeur ≤ 6).
SEARCH_SPACE = {
    "regressor__model__n_estimators": [300, 400],
    "regressor__model__max_depth": [5, 6],
    "regressor__model__learning_rate": [0.05, 0.08, 0.1, 0.15],
    "regressor__model__min_samples_leaf": [2, 5, 10],
    "regressor__model__subsample": [0.7, 0.8, 1.0],
}


# Réglages retenus par la recherche aléatoire (notebook, section 7).
FINAL_PARAMS = {
    "n_estimators": 400,
    "max_depth": 6,
    "learning_rate": 0.08,
    "min_samples_leaf": 5,
    "subsample": 1.0,
}


def kfold() -> KFold:
    """Validation croisée à 5 plis, mélangée et reproductible."""
    return KFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)


def split(
    features: pd.DataFrame, target: pd.Series
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Découpage unique entraînement / test (80 / 20)."""
    return train_test_split(features, target, test_size=TEST_SIZE, random_state=RANDOM_STATE)


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """MAE et RMSE (₹), MAPE (fraction) et R²."""
    return {
        "MAE": mean_absolute_error(y_true, y_pred),
        "RMSE": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "MAPE": mean_absolute_percentage_error(y_true, y_pred),
        "R2": r2_score(y_true, y_pred),
    }


def make_preprocessor(scale_numeric: bool = False) -> ColumnTransformer:
    """Encodage one-hot des variables qualitatives ; variables numériques standardisées si besoin.

    Les arbres n'ont pas besoin de standardisation : les numériques passent alors telles quelles.
    """
    onehot = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    numeric = StandardScaler() if scale_numeric else "passthrough"
    return ColumnTransformer(
        [("cat", onehot, CATEGORICAL_FEATURES), ("num", numeric, NUMERIC_FEATURES)],
        verbose_feature_names_out=False,
    )


def on_log_price(model: RegressorMixin, scale_numeric: bool = False) -> TransformedTargetRegressor:
    """Pipeline préparation + modèle, appris sur log(prix) puis retransformé en roupies.

    Les écarts de prix étant multiplicatifs (une escale renchérit le billet d'un pourcentage plutôt
    que d'un montant fixe), le logarithme stabilise la variance et réduit le poids des tarifs
    extrêmes.
    """
    pipeline = Pipeline([("prep", make_preprocessor(scale_numeric)), ("model", model)])
    return TransformedTargetRegressor(regressor=pipeline, func=np.log, inverse_func=np.exp)


def candidate_models() -> dict[str, RegressorMixin]:
    """Familles de modèles comparées, du plus simple au plus flexible."""
    return {
        "Référence (médiane)": Pipeline(
            [("prep", make_preprocessor()), ("model", DummyRegressor(strategy="median"))]
        ),
        "Régression ridge": on_log_price(Ridge(alpha=1.0), scale_numeric=True),
        "Arbre de décision": on_log_price(
            DecisionTreeRegressor(min_samples_leaf=3, random_state=RANDOM_STATE)
        ),
        "Forêt aléatoire": on_log_price(
            RandomForestRegressor(
                n_estimators=300, max_features=0.5, n_jobs=-1, random_state=RANDOM_STATE
            )
        ),
        "Gradient boosting": on_log_price(
            GradientBoostingRegressor(
                n_estimators=400,
                max_depth=6,
                learning_rate=0.08,
                min_samples_leaf=5,
                subsample=0.8,
                random_state=RANDOM_STATE,
            )
        ),
    }


def final_model() -> TransformedTargetRegressor:
    """Modèle retenu (non entraîné) : gradient boosting réglé, appris sur log(prix)."""
    return on_log_price(GradientBoostingRegressor(**FINAL_PARAMS, random_state=RANDOM_STATE))


def compare_models(
    models: dict[str, RegressorMixin], x_train: pd.DataFrame, y_train: pd.Series
) -> pd.DataFrame:
    """Validation croisée de chaque modèle : moyenne et écart-type de chaque métrique."""
    rows = []
    for name, model in models.items():
        start = time.perf_counter()
        scores = cross_validate(model, x_train, y_train, cv=kfold(), scoring=SCORING, n_jobs=-1)
        row = {"modèle": name}
        for metric in SCORING:
            values = scores[f"test_{metric}"] * (1 if metric == "R2" else -1)
            row[metric] = values.mean()
            row[f"{metric} (é.-t.)"] = values.std()
        row["durée (s)"] = time.perf_counter() - start
        rows.append(row)
    return pd.DataFrame(rows).set_index("modèle")


def tune_gradient_boosting(
    x_train: pd.DataFrame, y_train: pd.Series, n_iter: int = 12
) -> RandomizedSearchCV:
    """Recherche aléatoire des hyperparamètres du gradient boosting (sur l'entraînement seul)."""
    search = RandomizedSearchCV(
        on_log_price(GradientBoostingRegressor(random_state=RANDOM_STATE)),
        SEARCH_SPACE,
        n_iter=n_iter,
        scoring=SCORING,
        refit="RMSE",
        cv=kfold(),
        n_jobs=-1,
        random_state=RANDOM_STATE,
    )
    return search.fit(x_train, y_train)


def search_results(search: RandomizedSearchCV) -> pd.DataFrame:
    """Tableau lisible des combinaisons testées, de la meilleure à la moins bonne (RMSE)."""
    results = pd.DataFrame(search.cv_results_)
    params = results["params"].apply(
        lambda p: {k.removeprefix("regressor__model__"): v for k, v in p.items()}
    )
    table = pd.DataFrame(params.tolist())
    for metric in SCORING:
        sign = 1 if metric == "R2" else -1
        table[metric] = sign * results[f"mean_test_{metric}"]
    return table.sort_values("RMSE").reset_index(drop=True)


def evaluate_on_test(
    models: dict[str, RegressorMixin],
    x_train: pd.DataFrame,
    y_train: pd.Series,
    x_test: pd.DataFrame,
    y_test: pd.Series,
) -> tuple[pd.DataFrame, dict[str, RegressorMixin]]:
    """Réentraîne chaque modèle sur tout l'entraînement et le mesure une fois sur le test."""
    fitted, rows = {}, []
    for name, model in models.items():
        fitted[name] = clone(model).fit(x_train, y_train)
        rows.append({"modèle": name, **regression_metrics(y_test, fitted[name].predict(x_test))})
    return pd.DataFrame(rows).set_index("modèle"), fitted


def ratio_interval(
    model: RegressorMixin,
    x_train: pd.DataFrame,
    y_train: pd.Series,
    coverage: float = 0.8,
) -> tuple[float, float]:
    """Intervalle de prédiction multiplicatif, estimé sur les prédictions hors-pli (entraînement).

    Renvoie (bas, haut) tels que, pour `coverage` des vols, prix réel / prix prédit ∈ [bas, haut].
    """
    oof = cross_val_predict(model, x_train, y_train, cv=kfold(), n_jobs=-1)
    ratio = y_train.to_numpy() / oof
    tail = (1 - coverage) / 2
    low, high = np.quantile(ratio, [tail, 1 - tail])
    return float(low), float(high)


def feature_importances(
    model: RegressorMixin, x_test: pd.DataFrame, y_test: pd.Series, n_repeats: int = 5
) -> pd.DataFrame:
    """Importance par permutation (hausse de la MAE quand on mélange une variable), sur le test."""
    result = permutation_importance(
        model,
        x_test,
        y_test,
        scoring="neg_mean_absolute_error",
        n_repeats=n_repeats,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    return (
        pd.DataFrame(
            {"variable": x_test.columns, "hausse MAE (₹)": result.importances_mean},
        )
        .assign(**{"é.-t.": result.importances_std})
        .sort_values("hausse MAE (₹)", ascending=False)
        .reset_index(drop=True)
    )


def errors_by(
    groups: pd.Series, y_true: pd.Series, y_pred: np.ndarray, min_count: int = 20
) -> pd.DataFrame:
    """Erreurs du modèle par groupe (compagnie, tranche de prix…) : effectif, MAE, MAPE, biais."""
    frame = pd.DataFrame(
        {"groupe": groups.to_numpy(), "réel": y_true.to_numpy(), "prédit": np.asarray(y_pred)}
    )
    frame["erreur"] = frame["prédit"] - frame["réel"]
    summary = frame.groupby("groupe", observed=True).agg(
        vols=("réel", "size"),
        MAE=("erreur", lambda e: e.abs().mean()),
        biais=("erreur", "mean"),
    )
    summary["MAPE"] = (
        frame.assign(ape=frame["erreur"].abs() / frame["réel"])
        .groupby("groupe", observed=True)["ape"]
        .mean()
    )
    return summary[summary["vols"] >= min_count].sort_values("MAE")


def node_count(model: TransformedTargetRegressor) -> int:
    """Nombre total de nœuds des arbres d'un modèle d'ensemble (taille du modèle)."""
    trees = np.ravel(model.regressor_.named_steps["model"].estimators_)
    return int(sum(tree.tree_.node_count for tree in trees))
