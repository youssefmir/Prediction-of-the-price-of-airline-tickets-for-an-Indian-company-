"""Génère `docs/data.js`, les données du site interactif, et vérifie le modèle JavaScript.

Usage :
    python scripts/build_site_data.py          # relance toute l'étude (≈ 2 min)
    python scripts/build_site_data.py --reuse  # réutilise le dernier résultat (data/cache/)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from flight_prices.config import DOCS_DIR  # noqa: E402
from flight_prices.experiment import run_experiment  # noqa: E402
from flight_prices.parity import check_js  # noqa: E402
from flight_prices.site_data import build_site_data, write_data_js  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reuse", action="store_true", help="réutilise les résultats en cache")
    args = parser.parse_args()

    experiment = run_experiment(use_cache=args.reuse)
    data = build_site_data(experiment)
    size = write_data_js(data, DOCS_DIR / "data.js")
    print(f"docs/data.js écrit ({size / 1024:.0f} Ko)")

    test_flights = experiment.flights.loc[experiment.x_test.index]
    parity = check_js(data["model"], test_flights, experiment.test_predictions)
    print(
        f"Modèle JavaScript : {parity['n']} vols de test, écart maximal {parity['maxDiff']:.5f} ₹"
    )


if __name__ == "__main__":
    main()
