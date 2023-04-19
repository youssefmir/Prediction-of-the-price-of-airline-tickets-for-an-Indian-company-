"""Chemins, constantes et paramètres partagés par tout le projet."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
CACHE_DIR = PROJECT_ROOT / "data" / "cache"  # téléchargements (non versionnés)
DOCS_DIR = PROJECT_ROOT / "docs"
FIGURES_DIR = PROJECT_ROOT / "assets" / "figures"

RAW_FILE = DATA_RAW_DIR / "Data_Train.xlsx"

RANDOM_STATE = 42
TEST_SIZE = 0.20
CV_FOLDS = 5

# Taux de référence BCE, moyenne annuelle 2019 : 1 EUR = 78,8361 INR.
INR_PER_EUR_2019 = 78.8361

# Aéroports d'escale fréquents (≥ 100 vols dans les données) : une variable binaire chacun.
HUBS: tuple[str, ...] = ("BOM", "DEL", "HYD", "MAA", "AMD", "JAI", "BLR", "BBI", "IDR", "NAG")

# Villes du jeu de données → code IATA de l'aéroport principal.
CITY_IATA: dict[str, str] = {
    "Bangalore": "BLR",
    "Chennai": "MAA",
    "Cochin": "COK",
    "Delhi": "DEL",
    "Hyderabad": "HYD",
    "Kolkata": "CCU",
    "Mumbai": "BOM",
}

# Ville et coordonnées (latitude, longitude) de chaque aéroport cité dans les itinéraires.
AIRPORTS: dict[str, tuple[str, float, float]] = {
    "DEL": ("Delhi", 28.556, 77.100),
    "BOM": ("Mumbai", 19.089, 72.868),
    "BLR": ("Bangalore", 13.199, 77.706),
    "MAA": ("Chennai", 12.990, 80.169),
    "CCU": ("Kolkata", 22.654, 88.447),
    "HYD": ("Hyderabad", 17.240, 78.429),
    "COK": ("Cochin", 10.152, 76.402),
    "AMD": ("Ahmedabad", 23.077, 72.635),
    "JAI": ("Jaipur", 26.824, 75.812),
    "BBI": ("Bhubaneswar", 20.244, 85.818),
    "IDR": ("Indore", 22.722, 75.801),
    "NAG": ("Nagpur", 21.092, 79.047),
    "GAU": ("Guwahati", 26.106, 91.586),
    "GOI": ("Goa", 15.380, 73.831),
    "PNQ": ("Pune", 18.582, 73.920),
    "BHO": ("Bhopal", 23.287, 77.337),
    "LKO": ("Lucknow", 26.761, 80.889),
    "IXR": ("Ranchi", 23.314, 85.322),
    "JDH": ("Jodhpur", 26.251, 73.049),
    "ATQ": ("Amritsar", 31.710, 74.797),
    "BDQ": ("Vadodara", 22.336, 73.226),
    "VGA": ("Vijayawada", 16.530, 80.797),
    "TRV": ("Thiruvananthapuram", 8.482, 76.920),
    "UDR": ("Udaipur", 24.618, 73.896),
    "IXB": ("Bagdogra", 26.681, 88.328),
    "RPR": ("Raipur", 21.180, 81.739),
    "IXU": ("Aurangabad", 19.863, 75.398),
    "IXC": ("Chandigarh", 30.673, 76.788),
    "VNS": ("Varanasi", 25.452, 82.859),
    "PAT": ("Patna", 25.591, 85.088),
    "KNU": ("Kanpur", 26.404, 80.410),
    "GWL": ("Gwalior", 26.293, 78.228),
    "HBX": ("Hubli", 15.362, 75.085),
    "IMF": ("Imphal", 24.760, 93.897),
    "ISK": ("Nashik", 20.119, 73.913),
    "VTZ": ("Visakhapatnam", 17.721, 83.225),
    "DED": ("Dehradun", 30.190, 78.180),
    "STV": ("Surat", 21.115, 72.742),
    "IXZ": ("Port Blair", 11.641, 92.730),
    "NDC": ("Nanded", 19.183, 77.317),
    "IXA": ("Agartala", 23.887, 91.240),
    "JLR": ("Jabalpur", 23.178, 80.052),
}


def inr_to_eur(amount_inr: float) -> float:
    """Convertit un montant en roupies (₹) en euros au taux moyen 2019."""
    return amount_inr / INR_PER_EUR_2019
