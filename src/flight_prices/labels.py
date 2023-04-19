"""Libellés d'affichage en français, partagés par le notebook et le site."""

from __future__ import annotations

from .config import AIRPORTS, HUBS

# Indicatifs IATA des compagnies (2019) affichés sur le tableau des départs.
AIRLINE_CODES = {
    "Air Asia": "I5",
    "Air India": "AI",
    "GoAir": "G8",
    "IndiGo": "6E",
    "Jet Airways": "9W",
    "Multiple carriers": "MULTI",
    "SpiceJet": "SG",
    "Trujet": "2T",
    "Vistara": "UK",
}

FEATURE_LABELS = {
    "airline": "Compagnie",
    "cabin": "Cabine",
    "source": "Ville de départ",
    "destination": "Ville d'arrivée",
    "additional_info": "Conditions du billet",
    "n_stops": "Nombre d'escales",
    "duration_min": "Durée du trajet",
    "dep_minutes": "Heure de départ",
    "arr_minutes": "Heure d'arrivée",
    "arr_day_offset": "Arrivée le lendemain",
    "journey_day": "Jour du mois",
    "journey_month": "Mois du vol",
    "journey_weekday": "Jour de la semaine",
    "journey_doy": "Date du vol",
    **{f"via_{hub}": f"Escale à {AIRPORTS[hub][0]}" for hub in HUBS},
}

INFO_LABELS = {
    "No info": "Tarif standard",
    "In-flight meal not included": "Repas non inclus",
    "No check-in baggage included": "Sans bagage en soute",
    "Other": "Autre mention (rare)",
}

STOPS_LABELS = {0: "Direct", 1: "1 escale", 2: "2 escales", 3: "3 escales", 4: "4 escales"}

DURATION_BINS = [0, 180, 360, 600, 900, 1200, 1800, 3000]
DURATION_LABELS = ["< 3 h", "3–6 h", "6–10 h", "10–15 h", "15–20 h", "20–30 h", "> 30 h"]


def fr(value: float, decimals: int = 0, unit: str = "") -> str:
    """Nombre à la française : espace fine insécable entre milliers, virgule décimale.

    >>> fr(12345.678, 1, "₹")
    '12 345,7 ₹'
    """
    text = f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")
    text = text.replace("-", "−")
    return f"{text} {unit}" if unit else text


def fr_pct(fraction: float, decimals: int = 1, signed: bool = False) -> str:
    """Fraction → pourcentage à la française : 0.0686 → « 6,9 % » (« +6,9 % » si `signed`)."""
    sign = "+" if signed and fraction > 0 else ""
    return sign + fr(fraction * 100, decimals, "%")
