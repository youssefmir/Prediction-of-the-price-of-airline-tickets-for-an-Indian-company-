"""Vérification croisée Python / JavaScript du modèle exporté vers le navigateur."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import HUBS, PROJECT_ROOT
from .features import INFO_KEPT

CHECK_SCRIPT = PROJECT_ROOT / "scripts" / "check_js_model.js"
JS_SPEC = {"hubs": list(HUBS), "infoKept": list(INFO_KEPT)}


def simulator_inputs(flights: pd.DataFrame) -> list[dict[str, Any]]:
    """Traduit des vols (table nettoyée) en saisies du simulateur du site."""
    return [
        {
            "airline": r.airline,
            "cabin": r.cabin,
            "source": r.source,
            "destination": r.destination,
            "route": r.route,
            "date": r.journey_date.strftime("%Y-%m-%d"),
            "dep": r.dep_time,
            "duration": int(r.duration_min),
            "info": r.additional_info,
        }
        for r in flights.itertuples()
    ]


def check_js(
    exported: dict[str, Any], flights: pd.DataFrame, expected: np.ndarray, tolerance: float = 0.01
) -> dict[str, float]:
    """Fait prédire `docs/model.js` (Node) sur `flights` et compare à `expected` (₹).

    Renvoie {"n": nombre de vols, "maxDiff": écart absolu maximal}. Lève une erreur au-delà de
    `tolerance`.
    """
    cases = [
        {"input": inp, "expected": float(exp)}
        for inp, exp in zip(simulator_inputs(flights), expected, strict=True)
    ]
    payload = {"model": exported, "spec": JS_SPEC, "cases": cases}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "cases.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        run = subprocess.run(
            ["node", str(CHECK_SCRIPT), str(path), str(tolerance)],
            capture_output=True,
            text=True,
            check=False,
        )
    if run.returncode not in (0, 1):
        raise RuntimeError(run.stderr)
    result = json.loads(run.stdout)
    if run.returncode == 1:
        raise AssertionError(f"Écart Python / JavaScript trop grand : {result}")
    return result
