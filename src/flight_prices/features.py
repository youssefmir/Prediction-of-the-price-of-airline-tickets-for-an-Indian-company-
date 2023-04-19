"""Variables explicatives construites à partir de la table nettoyée.

Toutes les variables se calculent à partir de ce qu'un voyageur connaît au moment de chercher un
vol : compagnie, cabine, itinéraire, date, heure de départ et durée. Le même calcul est réimplémenté
en JavaScript pour le simulateur du site (`docs/model.js`) : toute modification ici doit y être
reportée (le test `tests/test_js_parity.py` le vérifie).
"""

from __future__ import annotations

import pandas as pd

from .config import HUBS

MINUTES_PER_DAY = 24 * 60

# Informations complémentaires rares (< 20 vols) regroupées dans « Other ».
INFO_KEPT = ("No info", "In-flight meal not included", "No check-in baggage included")

CATEGORICAL_FEATURES = ["airline", "cabin", "source", "destination", "additional_info"]
NUMERIC_FEATURES = [
    "n_stops",
    "duration_min",
    "dep_minutes",
    "arr_minutes",
    "arr_day_offset",
    "journey_day",
    "journey_month",
    "journey_weekday",
    "journey_doy",
    *(f"via_{hub}" for hub in HUBS),
]
FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES


def clock_to_minutes(clock: str) -> int:
    """« 05:50 » → 350 minutes depuis minuit."""
    hours, minutes = clock[:5].split(":")
    return int(hours) * 60 + int(minutes)


def layovers(route: str) -> list[str]:
    """Aéroports d'escale d'un itinéraire « CCU → IXR → BBI → BLR » → [« IXR », « BBI »]."""
    return [code.strip() for code in route.split("→")][1:-1]


def group_info(info: str) -> str:
    """Regroupe les informations complémentaires rares dans « Other »."""
    return info if info in INFO_KEPT else "Other"


def build_features(tidy: pd.DataFrame) -> pd.DataFrame:
    """Construit la matrice des variables explicatives (colonnes `FEATURES`).

    - date du voyage → jour, mois, jour de la semaine (0 = lundi), jour de l'année ;
    - heure de départ → minutes depuis minuit ; arrivée = départ + durée (heure et jour) ;
    - itinéraire → une variable binaire par aéroport d'escale fréquent (`HUBS`).
    """
    dep = tidy["dep_time"].map(clock_to_minutes)
    end = dep + tidy["duration_min"]
    date = tidy["journey_date"]
    stops = tidy["route"].map(layovers)

    features = pd.DataFrame(
        {
            "airline": tidy["airline"],
            "cabin": tidy["cabin"],
            "source": tidy["source"],
            "destination": tidy["destination"],
            "additional_info": tidy["additional_info"].map(group_info),
            "n_stops": tidy["n_stops"],
            "duration_min": tidy["duration_min"],
            "dep_minutes": dep,
            "arr_minutes": end % MINUTES_PER_DAY,
            "arr_day_offset": end // MINUTES_PER_DAY,
            "journey_day": date.dt.day,
            "journey_month": date.dt.month,
            "journey_weekday": date.dt.dayofweek,
            "journey_doy": date.dt.dayofyear,
        },
        index=tidy.index,
    )
    for hub in HUBS:
        features[f"via_{hub}"] = stops.map(lambda codes, hub=hub: int(hub in codes))
    return features[FEATURES]


def count_conflicts(features: pd.DataFrame, prices: pd.Series) -> int:
    """Nombre de combinaisons de variables strictement identiques observées avec plusieurs prix.

    Aucun modèle ne peut départager ces vols : c'est une borne basse de l'erreur atteignable.
    """
    distinct = features.assign(price=prices).groupby(list(features.columns))["price"].nunique()
    return int((distinct > 1).sum())
