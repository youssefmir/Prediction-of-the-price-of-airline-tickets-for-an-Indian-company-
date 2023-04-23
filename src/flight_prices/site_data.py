"""Données du site interactif (`docs/data.js`), calculées à partir des résultats de l'étude."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import CITY_IATA, HUBS, INR_PER_EUR_2019, RANDOM_STATE
from .experiment import FINAL_NAME, Experiment
from .export import export_model
from .features import INFO_KEPT, layovers
from .geo import airport_positions, load_simplified_outline, outline_svg
from .labels import AIRLINE_CODES, DURATION_BINS, DURATION_LABELS, FEATURE_LABELS, INFO_LABELS

BOARD_SAMPLE = {"Delhi": 2, "Kolkata": 2, "Bangalore": 2, "Mumbai": 1, "Chennai": 1}
STRIP_SIZE = 2400  # vols tirés au hasard pour le nuage de points de la section « prix »
STOPS_LABELS = ["Direct", "1 escale", "2 escales", "3 escales ou plus"]
PERIODS = [
    ("1er – 9 mars", "2019-03-09"),
    ("10 – 31 mars", "2019-03-31"),
    ("Avril", "2019-04-30"),
    ("Mai", "2019-05-31"),
    ("Juin", "2019-06-30"),
]


def _r(value: float, digits: int = 0) -> float | int:
    """Arrondi compact pour le JSON."""
    return int(round(value)) if digits == 0 else round(float(value), digits)


def _metrics(row: pd.Series) -> dict[str, float | int]:
    """MAE et RMSE arrondies au roupie près, MAPE et R² à 4 décimales."""
    return {
        k: _r(row[k], 4) if k in ("MAPE", "R2") else _r(row[k])
        for k in ("MAE", "RMSE", "MAPE", "R2")
    }


def price_summary(prices: pd.Series) -> dict[str, Any]:
    """Effectif et quartiles d'une série de prix (₹)."""
    q = prices.quantile([0.25, 0.5, 0.75])
    return {"n": int(prices.size), "q1": _r(q[0.25]), "median": _r(q[0.5]), "q3": _r(q[0.75])}


def groupings(flights: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, list[dict]]]:
    """Groupes de chaque étape du récit : escales, compagnie, durée, période du vol.

    Renvoie l'indice de groupe de chaque vol (NaN si hors groupe) et, pour chaque regroupement,
    l'effectif et le prix médian de chaque groupe, calculés sur tous les vols.
    """
    airlines = flights.groupby("airline")["price"].agg(["size", "median"])
    airlines = airlines[airlines["size"] >= 20].sort_values("median")
    order = list(airlines.index)
    period_ends = pd.to_datetime([end for _, end in PERIODS])
    index = pd.DataFrame(
        {
            "stops": flights["n_stops"].clip(upper=3),
            "airline": flights["airline"].map({a: i for i, a in enumerate(order)}),
            "duration": pd.cut(flights["duration_min"], DURATION_BINS, labels=False, right=False),
            "period": np.searchsorted(period_ends, flights["journey_date"]),
        },
        index=flights.index,
    )
    labels = {
        "stops": STOPS_LABELS,
        "airline": order,
        "duration": DURATION_LABELS,
        "period": [label for label, _ in PERIODS],
    }
    groups = {}
    for key, names in labels.items():
        stats = flights.groupby(index[key])["price"].agg(["size", "median"])
        groups[key] = [
            {"label": names[int(i)], "n": int(row["size"]), "median": _r(row["median"])}
            for i, row in stats.iterrows()
        ]
    for group in groups["airline"]:
        group["code"] = AIRLINE_CODES[group["label"]]
    return index, groups


def strip(flights: pd.DataFrame) -> dict[str, Any]:
    """Échantillon de vols du nuage animé : [prix, escales, compagnie, durée, période]."""
    index, groups = groupings(flights)
    eligible = index.dropna().index.to_numpy()
    rng = np.random.default_rng(RANDOM_STATE)
    chosen = np.sort(rng.choice(eligible, size=STRIP_SIZE, replace=False))
    columns = [flights.loc[chosen, "price"], *(index.loc[chosen, k] for k in groups)]
    rows = np.column_stack(columns).astype(int).tolist()
    prices = flights["price"]
    return {
        "keys": list(groups),
        "rows": rows,
        "groups": groups,
        "overall": {
            "n": int(prices.size),
            "median": _r(prices.median()),
            "min": int(prices.min()),
            "max": int(prices.max()),
        },
    }


def network(flights: pd.DataFrame) -> dict[str, Any]:
    """Carte : contour de l'Inde, aéroports, liaisons (ville à ville) et itinéraires détaillés."""
    path, project = outline_svg(load_simplified_outline())
    pairs = []
    for (src, dst), group in flights.groupby(["source", "destination"]):
        routes = [
            {
                "codes": [c.strip() for c in route.split("→")],
                "n": int(len(g)),
                "median": _r(g["price"].median()),
            }
            for route, g in group.groupby("route")
            if len(g) >= 10
        ]
        pairs.append(
            {
                "from": CITY_IATA[src],
                "to": CITY_IATA[dst],
                "fromName": src,
                "toName": dst,
                **price_summary(group["price"]),
                "routes": sorted(routes, key=lambda r: -r["n"]),
            }
        )
    hubs = flights["route"].map(layovers).explode().value_counts()
    codes = sorted(flights["route"].str.split(" → ").explode().unique())
    return {
        "width": project.width,
        "height": _r(project.height, 1),
        "outline": path,
        "airports": airport_positions(project, codes),
        "cities": sorted(CITY_IATA.values()),
        "hubs": [{"code": c, "n": int(n)} for c, n in hubs.items()],
        "pairs": sorted(pairs, key=lambda p: -p["n"]),
    }


def board(exp: Experiment) -> list[dict]:
    """Vols du jeu de test affichés sur le tableau des départs (tirés au hasard, graine fixe)."""
    test = exp.flights.loc[exp.x_test.index].assign(pred=exp.test_predictions)
    rng = np.random.default_rng(RANDOM_STATE)
    rows = []
    for source, count in BOARD_SAMPLE.items():
        pool = test[(test["source"] == source) & (test["cabin"] == "Economy")]
        rows.append(pool.iloc[rng.choice(len(pool), size=count, replace=False)])
    sample = pd.concat(rows).sort_values("dep_time")
    return [
        {
            "code": AIRLINE_CODES[r.airline],
            "airline": r.airline,
            "date": r.journey_date.strftime("%Y-%m-%d"),
            "route": [c.strip() for c in r.route.split("→")],
            "dep": r.dep_time,
            "price": int(r.price),
            "pred": _r(r.pred),
        }
        for r in sample.itertuples()
    ]


def models(exp: Experiment) -> dict[str, Any]:
    """Classement des modèles (validation croisée et test) et importance des variables."""
    cv = [
        {
            "model": name,
            **_metrics(row),
            "MAE_sd": _r(row["MAE (é.-t.)"]),
            "RMSE_sd": _r(row["RMSE (é.-t.)"]),
            "R2_sd": _r(row["R2 (é.-t.)"], 4),
        }
        for name, row in exp.cv_table.iterrows()
    ]
    return {
        "cv": cv,
        "tuned": _metrics(exp.search_table.iloc[0]),
        "params": {k: v.item() if hasattr(v, "item") else v for k, v in exp.best_params.items()},
        "test": [{"model": name, **_metrics(row)} for name, row in exp.test_table.iterrows()],
        "importance": [
            {"feature": FEATURE_LABELS[r.variable], "value": _r(r[2]), "sd": _r(r[3])}
            for r in exp.importances.head(10).itertuples()
        ],
    }


def cloud(exp: Experiment) -> dict[str, Any]:
    """Prix réels et prédits des vols du test, et prédiction du modèle de référence (médiane)."""
    return {
        "actual": exp.y_test.astype(int).tolist(),
        "pred": np.round(exp.test_predictions).astype(int).tolist(),
        "reference": _r(exp.y_train.median()),
    }


def simulator(exp: Experiment) -> dict[str, Any]:
    """Options réalistes du simulateur : itinéraires, horaires et durées observés par compagnie."""
    options = []
    for (src, dst), pair in exp.flights.groupby(["source", "destination"]):
        airlines = []
        for airline, g in pair.groupby("airline"):
            if len(g) < 15:
                continue
            routes = [
                {
                    "route": route,
                    "n": int(len(r)),
                    "duration": _r(r["duration_min"].median()),
                    "deps": r["dep_time"].value_counts().head(6).index.tolist(),
                    "median": _r(r["price"].median()),
                }
                for route, r in g.groupby("route")
                if len(r) >= 5
            ]
            infos = g["additional_info"].value_counts()
            airlines.append(
                {
                    "airline": airline,
                    "cabins": sorted(g["cabin"].unique().tolist()),
                    "infos": [i for i in INFO_KEPT if infos.get(i, 0) >= 5],
                    "routes": sorted(routes, key=lambda r: -r["n"]),
                }
            )
        options.append({"source": src, "destination": dst, "airlines": airlines})
    return {
        "pairs": options,
        "hubs": list(HUBS),
        "infoKept": list(INFO_KEPT),
        "infoLabels": INFO_LABELS,
        "interval": [round(v, 4) for v in exp.interval],
        "codes": AIRLINE_CODES,
    }


def build_site_data(exp: Experiment) -> dict[str, Any]:
    """Assemble toutes les données du site."""
    flights = exp.flights
    business = exp.tidy.loc[exp.tidy["cabin"] == "Business", "price"]
    final = exp.final_model.regressor_.named_steps["model"]
    return {
        "meta": {
            "rawRows": int(exp.report.steps[0][1] + exp.report.steps[0][2]),
            "duplicates": int(exp.report.steps[1][1]),
            "flights": int(len(flights)),
            "train": int(len(exp.x_train)),
            "test": int(len(exp.x_test)),
            "airlines": int(flights["airline"].nunique()),
            "routes": int(flights["route"].nunique()),
            "business": {
                "n": int(business.size),
                "min": int(business.min()),
                "max": int(business.max()),
            },
            "inrPerEur": INR_PER_EUR_2019,
            "medianPrice": _r(flights["price"].median()),
            "conflicts": exp.conflicts,
            "nodes": {"gb": exp.model_nodes[FINAL_NAME], "rf": exp.model_nodes["Forêt aléatoire"]},
            "trees": len(final.estimators_),
        },
        "kpi": _metrics(exp.test_table.loc[FINAL_NAME]),
        "board": board(exp),
        "map": network(flights),
        "strip": strip(flights),
        "models": models(exp),
        "cloud": cloud(exp),
        "simulator": simulator(exp),
        "model": export_model(exp.final_model),
    }


def write_data_js(data: dict[str, Any], path: Path) -> int:
    """Écrit `window.SITE_DATA = {...};` et renvoie la taille du fichier (octets)."""
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    text = (
        "/* Fichier généré par scripts/build_site_data.py : ne pas modifier à la main. */\n"
        f"window.SITE_DATA = {payload};\n"
    )
    path.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))
