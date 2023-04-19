"""Tests de fumée des graphiques du notebook (rendu sans erreur, sans affichage)."""

import matplotlib

matplotlib.use("Agg")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from flight_prices import plotting  # noqa: E402

PRICES = pd.DataFrame(
    {
        "journey_date": pd.to_datetime(["2019-03-01", "2019-03-01", "2019-04-03", "2019-04-03"]),
        "group": ["a", "b", "a", "b"],
        "price": [18000, 16000, 4500, 5200],
    }
)


@pytest.mark.parametrize(
    "draw",
    [
        lambda ax: plotting.price_boxes(PRICES, "group", ax),
        lambda ax: plotting.median_price_by_date(PRICES, ax),
        lambda ax: plotting.predicted_vs_actual(
            np.array([3000.0, 9000.0]), np.array([3100.0, 8500.0]), ax, interval=(0.9, 1.1)
        ),
    ],
)
def test_charts_render(draw):
    fig, ax = plotting.new_figure()
    draw(ax)
    fig.canvas.draw()
    plotting.plt.close(fig)
