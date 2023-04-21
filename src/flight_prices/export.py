"""Export du modèle final vers un format JSON compact, évaluable dans le navigateur.

Format (`docs/model.js` l'évalue) :
- `columns` : une entrée par colonne d'entrée du modèle, dans l'ordre —
  `["cat", variable, modalité]` (indicatrice one-hot) ou `["num", variable]` ;
- `init` : prédiction initiale du gradient boosting (en log du prix) ;
- `trees` : arbres en parcours préfixe, trois tableaux parallèles par arbre :
  `f` (indice de colonne, −1 pour une feuille), `v` (seuil, ou valeur de la feuille déjà multipliée
  par le taux d'apprentissage), `r` (indice de l'enfant droit ; l'enfant gauche suit le nœud).
  On descend à gauche si `x[f] <= v`, comme scikit-learn.
- prix prédit = exp(init + Σ feuilles).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.tree import DecisionTreeRegressor

LEAF = -1
VALUE_DECIMALS = 9  # précision des feuilles : écart final < 0,01 ₹ sur le prix


def _columns(prep) -> list[list[str]]:
    """Décrit chaque colonne produite par le ColumnTransformer (one-hot puis numériques)."""
    columns: list[list[str]] = []
    for name, transformer, features in prep.transformers_:
        if name == "cat":
            for feature, categories in zip(features, transformer.categories_, strict=True):
                columns.extend(["cat", feature, str(category)] for category in categories)
        elif name == "num":
            if transformer != "passthrough":
                raise ValueError(
                    "Seules les variables numériques non transformées sont exportables."
                )
            columns.extend(["num", feature] for feature in features)
    return columns


def _tree(tree: DecisionTreeRegressor, scale: float) -> dict[str, list]:
    """Réordonne un arbre scikit-learn en parcours préfixe (enfant gauche juste après le parent)."""
    t = tree.tree_
    f: list[int] = []
    v: list[float] = []
    r: list[int] = []

    def visit(node: int) -> None:
        index = len(f)
        if t.children_left[node] == LEAF:
            f.append(LEAF)
            v.append(round(float(t.value[node][0][0]) * scale, VALUE_DECIMALS))
            r.append(0)
            return
        f.append(int(t.feature[node]))
        v.append(float(t.threshold[node]))
        r.append(0)
        visit(t.children_left[node])
        r[index] = len(f)
        visit(t.children_right[node])

    visit(0)
    return {"f": f, "v": v, "r": r}


def export_model(model: TransformedTargetRegressor) -> dict[str, Any]:
    """Convertit le pipeline final (log-prix → gradient boosting) en dictionnaire JSON."""
    pipeline = model.regressor_
    prep, gbr = pipeline.named_steps["prep"], pipeline.named_steps["model"]
    if not isinstance(gbr, GradientBoostingRegressor):
        raise TypeError("Export prévu pour un GradientBoostingRegressor.")
    init = float(np.ravel(gbr.init_.constant_)[0])
    return {
        "columns": _columns(prep),
        "init": init,
        "trees": [_tree(stage[0], gbr.learning_rate) for stage in gbr.estimators_],
    }


def encode(exported: dict[str, Any], features: pd.DataFrame) -> np.ndarray:
    """Encode une matrice de variables selon la description `columns` de l'export."""
    out = np.zeros((len(features), len(exported["columns"])))
    for j, column in enumerate(exported["columns"]):
        if column[0] == "cat":
            out[:, j] = (features[column[1]].astype(str) == column[2]).to_numpy()
        else:
            out[:, j] = features[column[1]].to_numpy(dtype=float)
    return out


def predict_exported(exported: dict[str, Any], features: pd.DataFrame) -> np.ndarray:
    """Prédiction de référence en Python à partir de l'export (miroir de `docs/model.js`)."""
    x = encode(exported, features)
    raw = np.full(len(x), exported["init"])
    for tree in exported["trees"]:
        f, v, r = tree["f"], tree["v"], tree["r"]
        for i, row in enumerate(x):
            node = 0
            while f[node] != LEAF:
                node = node + 1 if row[f[node]] <= v[node] else r[node]
            raw[i] += v[node]
    return np.exp(raw)
