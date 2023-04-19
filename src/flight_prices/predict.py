"""Prédire le prix d'un vol avec le modèle retenu : l'API la plus simple pour réutiliser le projet.

Exemple :
    >>> model = train_model()  # quelques secondes
    >>> flight = Flight("IndiGo", "Bangalore", "Delhi", "BLR → DEL", "2019-05-24", "06:05", 165)
    >>> round(predict_price(model, flight), -2)  # ₹
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd
from sklearn.compose import TransformedTargetRegressor

from . import modeling
from .data import TIDY_COLUMNS, clean, economy_only, load_raw
from .features import build_features


@dataclass
class Flight:
    """Un vol tel qu'un voyageur le voit au moment de chercher un billet."""

    airline: str  # « IndiGo », « Jet Airways », « Air India »…
    source: str  # ville de départ : « Bangalore », « Chennai », « Delhi », « Kolkata », « Mumbai »
    destination: str  # « Delhi », « Kolkata », « Cochin », « Bangalore », « Hyderabad »
    route: str  # itinéraire en codes IATA : « DEL → BOM → COK »
    date: str  # date du vol, « AAAA-MM-JJ » (le modèle a appris sur mars–juin 2019)
    dep_time: str  # heure de départ « HH:MM »
    duration_min: int  # durée totale du trajet, en minutes
    additional_info: str = "No info"  # ou « In-flight meal not included », etc.
    cabin: str = "Economy"  # ou « Premium economy »


def train_model() -> TransformedTargetRegressor:
    """Entraîne le modèle retenu sur le jeu d'entraînement (mêmes données que le site)."""
    flights = economy_only(clean(load_raw())[0])
    x_train, _, y_train, _ = modeling.split(build_features(flights), flights["price"])
    return modeling.final_model().fit(x_train, y_train)


def to_table(flights: list[Flight]) -> pd.DataFrame:
    """Convertit des vols en table au format de `data.clean` (prix inconnu)."""
    table = pd.DataFrame([asdict(f) for f in flights]).rename(columns={"date": "journey_date"})
    table["journey_date"] = pd.to_datetime(table["journey_date"], format="%Y-%m-%d")
    table["n_stops"] = table["route"].str.count("→") - 1
    table["price"] = 0
    return table[TIDY_COLUMNS]


def predict_price(model: TransformedTargetRegressor, flight: Flight) -> float:
    """Prix prédit (₹) pour un vol."""
    return float(model.predict(build_features(to_table([flight])))[0])
