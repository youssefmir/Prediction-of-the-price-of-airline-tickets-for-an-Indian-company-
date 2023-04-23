"""Régénère `data/raw/india_outline_simplified.geojson` à partir du contour DataMeet.

Usage :
    python scripts/simplify_outline.py
Le contour d'origine (~10 Mo, CC BY 4.0) est téléchargé dans `data/cache/` au premier lancement.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from flight_prices.geo import write_simplified_outline  # noqa: E402


def main() -> None:
    path = write_simplified_outline()
    print(f"{path.name} écrit ({path.stat().st_size / 1024:.0f} Ko)")


if __name__ == "__main__":
    main()
