"""Chargement et nettoyage du jeu de données des vols intérieurs indiens (mars–juin 2019)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .config import RAW_FILE

# Libellés du fichier source → libellés harmonisés.
CITY_FIXES = {"Banglore": "Bangalore", "New Delhi": "Delhi"}
INFO_FIXES = {"No Info": "No info"}
STOPS = {"non-stop": 0, "1 stop": 1, "2 stops": 2, "3 stops": 3, "4 stops": 4}
CABIN_SUFFIXES = {" Business": "Business", " Premium economy": "Premium economy"}
MIN_DURATION_MIN = 60  # en dessous, la durée est une erreur de saisie (ex. « 5m » pour 3 vols)

TIDY_COLUMNS = [
    "airline",
    "cabin",
    "source",
    "destination",
    "route",
    "journey_date",
    "dep_time",
    "duration_min",
    "n_stops",
    "additional_info",
    "price",
]


@dataclass
class CleaningReport:
    """Journal des étapes de nettoyage : (étape, lignes retirées, lignes restantes)."""

    steps: list[tuple[str, int, int]] = field(default_factory=list)

    def log(self, step: str, before: int, after: int) -> None:
        self.steps.append((step, before - after, after))

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.steps, columns=["étape", "lignes retirées", "lignes restantes"])


def load_raw(path: Path = RAW_FILE) -> pd.DataFrame:
    """Lit le fichier Excel d'origine (10 683 vols, 11 colonnes)."""
    return pd.read_excel(path)


def parse_duration(text: str) -> int:
    """Convertit une durée « 2h 50m », « 19h » ou « 5m » en minutes."""
    hours = minutes = 0
    for token in str(text).split():
        if token.endswith("h"):
            hours = int(token[:-1])
        elif token.endswith("m"):
            minutes = int(token[:-1])
        else:
            raise ValueError(f"Durée illisible : {text!r}")
    return hours * 60 + minutes


def split_airline_cabin(label: str) -> tuple[str, str]:
    """Sépare compagnie et cabine : « Jet Airways Business » → (« Jet Airways », « Business »)."""
    for suffix, cabin in CABIN_SUFFIXES.items():
        if label.endswith(suffix):
            return label.removesuffix(suffix), cabin
    return label, "Economy"


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
    """Nettoie les données brutes et renvoie une table typée « tidy » et le journal des étapes.

    Étapes : harmonisation des libellés, suppression de la ligne incomplète, des doublons exacts
    et des durées impossibles, séparation compagnie / cabine, typage des colonnes.
    """
    report = CleaningReport()
    frame = raw.copy()
    n = len(frame)

    text_cols = frame.select_dtypes(include=["object", "string"]).columns
    frame[text_cols] = frame[text_cols].apply(lambda s: s.str.strip())
    frame["Additional_Info"] = frame["Additional_Info"].replace(INFO_FIXES)
    frame[["Source", "Destination"]] = frame[["Source", "Destination"]].replace(CITY_FIXES)

    frame = frame.dropna()
    report.log("ligne incomplète (itinéraire et escales manquants)", n, len(frame))

    n = len(frame)
    frame = frame.drop_duplicates()
    report.log("doublons exacts", n, len(frame))

    duration = frame["Duration"].map(parse_duration)
    n = len(frame)
    frame = frame[duration >= MIN_DURATION_MIN]
    report.log(f"durée < {MIN_DURATION_MIN} min (erreur de saisie)", n, len(frame))

    airline_cabin = frame["Airline"].map(split_airline_cabin)
    tidy = pd.DataFrame(
        {
            "airline": airline_cabin.str[0],
            "cabin": airline_cabin.str[1],
            "source": frame["Source"],
            "destination": frame["Destination"],
            "route": frame["Route"],
            "journey_date": pd.to_datetime(frame["Date_of_Journey"], format="%d/%m/%Y"),
            "dep_time": frame["Dep_Time"],
            "duration_min": frame["Duration"].map(parse_duration).astype(int),
            "n_stops": frame["Total_Stops"].map(STOPS).astype(int),
            "additional_info": frame["Additional_Info"],
            "price": frame["Price"].astype(int),
        }
    )
    # « Business class » dans les informations complémentaires = billet en classe affaires.
    tidy.loc[tidy["additional_info"].eq("Business class"), "cabin"] = "Business"
    return tidy.reset_index(drop=True)[TIDY_COLUMNS], report


def economy_only(tidy: pd.DataFrame) -> pd.DataFrame:
    """Périmètre de modélisation : cabines économique et premium économique.

    Les 7 billets en classe affaires (46 000 à 80 000 ₹) forment un autre produit, trop rare
    pour être appris : ils sont décrits à part et exclus du modèle.
    """
    return tidy[tidy["cabin"] != "Business"].reset_index(drop=True)
