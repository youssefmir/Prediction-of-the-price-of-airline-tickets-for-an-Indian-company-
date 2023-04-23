"""Fond de carte de l'Inde pour la carte des liaisons du site.

Source : contour « India composite » de la communauté DataMeet (CC BY 4.0), qui suit les
frontières officielles de l'Inde. Le fichier d'origine (~10 Mo) est téléchargé dans `data/cache/`
(non versionné) ; sa version simplifiée (~15 Ko) est versionnée dans `data/raw/` et se régénère
avec `scripts/simplify_outline.py`.
"""

from __future__ import annotations

import json
import math
import urllib.request
from pathlib import Path

from shapely.geometry import MultiPolygon, mapping, shape

from .config import AIRPORTS, CACHE_DIR, DATA_RAW_DIR

SOURCE_URL = (
    "https://raw.githubusercontent.com/datameet/maps/master/Country/india-composite.geojson"
)
SOURCE_FILE = CACHE_DIR / "india-composite.geojson"
SIMPLIFIED_FILE = DATA_RAW_DIR / "india_outline_simplified.geojson"
ATTRIBUTION = "India boundaries par la communauté DataMeet (CC BY 4.0)"

TOLERANCE_DEG = 0.04  # simplification (Douglas-Peucker), en degrés
MIN_AREA_DEG2 = 0.05  # îles plus petites omises
DECIMALS = 4  # ≈ 10 m


def download_source(path: Path = SOURCE_FILE) -> Path:
    """Télécharge le contour d'origine de DataMeet s'il n'est pas déjà en cache."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(SOURCE_URL, path)  # noqa: S310 (URL fixe, HTTPS)
    return path


def _as_multipolygon(geometry) -> MultiPolygon:
    return geometry if isinstance(geometry, MultiPolygon) else MultiPolygon([geometry])


def simplify_outline(
    source: Path = SOURCE_FILE, tolerance: float = TOLERANCE_DEG, min_area: float = MIN_AREA_DEG2
) -> MultiPolygon:
    """Simplifie le contour d'origine et retire les plus petites îles."""
    collection = json.loads(download_source(source).read_text(encoding="utf-8"))
    outline = _as_multipolygon(shape(collection["features"][0]["geometry"]))
    parts = [p.simplify(tolerance, preserve_topology=True) for p in outline.geoms]
    return MultiPolygon([p for p in parts if p.area >= min_area and not p.is_empty])


def _rounded(coords, decimals: int):
    if isinstance(coords[0], int | float):
        return [round(c, decimals) for c in coords]
    return [_rounded(c, decimals) for c in coords]


def write_simplified_outline(path: Path = SIMPLIFIED_FILE) -> Path:
    """Écrit la version simplifiée versionnée dans `data/raw/` (GeoJSON)."""
    geometry = mapping(simplify_outline())
    feature = {
        "type": "Feature",
        "properties": {
            "source": SOURCE_URL,
            "attribution": ATTRIBUTION,
            "simplification": (
                f"Douglas-Peucker {TOLERANCE_DEG}°, îles < {MIN_AREA_DEG2} deg² omises"
            ),
        },
        "geometry": {
            "type": geometry["type"],
            "coordinates": _rounded(geometry["coordinates"], DECIMALS),
        },
    }
    collection = {"type": "FeatureCollection", "features": [feature]}
    path.write_text(json.dumps(collection, ensure_ascii=False, separators=(",", ":")), "utf-8")
    return path


def load_simplified_outline(path: Path = SIMPLIFIED_FILE) -> MultiPolygon:
    """Lit le contour simplifié versionné."""
    collection = json.loads(path.read_text(encoding="utf-8"))
    return _as_multipolygon(shape(collection["features"][0]["geometry"]))


def _mercator_y(lat: float) -> float:
    """Ordonnée Mercator, exprimée en « degrés » pour garder la même unité que la longitude."""
    return math.degrees(math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


class Projection:
    """Projection Mercator ajustée à une boîte englobante, vers un repère SVG de largeur `width`."""

    def __init__(self, bounds: tuple[float, float, float, float], width: float = 1000.0):
        lon_min, lat_min, lon_max, lat_max = bounds
        self.lon_min = lon_min
        self.y_top = _mercator_y(lat_max)
        self.scale = width / (lon_max - lon_min)
        self.width = width
        self.height = (self.y_top - _mercator_y(lat_min)) * self.scale

    def __call__(self, lon: float, lat: float) -> tuple[float, float]:
        x = (lon - self.lon_min) * self.scale
        y = (self.y_top - _mercator_y(lat)) * self.scale
        return round(x, 1), round(y, 1)


def outline_svg(outline: MultiPolygon, width: float = 1000.0) -> tuple[str, Projection]:
    """Projette le contour et le convertit en attribut `d` d'un chemin SVG."""
    project = Projection(outline.bounds, width)
    paths = []
    for polygon in outline.geoms:
        head, *tail = (project(lon, lat) for lon, lat in polygon.exterior.coords)
        paths.append(f"M{head[0]} {head[1]}" + "".join(f"L{x} {y}" for x, y in tail) + "Z")
    return "".join(paths), project


def airport_positions(project: Projection, codes: list[str]) -> dict[str, dict]:
    """Nom et position projetée de chaque aéroport demandé."""
    out = {}
    for code in codes:
        name, lat, lon = AIRPORTS[code]
        x, y = project(lon, lat)
        out[code] = {"name": name, "x": x, "y": y}
    return out
