"""Style et graphiques du notebook, alignés sur la palette du site (`docs/styles.css`)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.ticker import FixedLocator, FuncFormatter, MaxNLocator, NullFormatter

from .config import FIGURES_DIR
from .labels import fr_pct

INK = "#141834"
INK_2 = "#444a6b"
MUTED = "#6b7090"
GRID = "#e3e5ee"
AXIS = "#c3c7d6"
SURFACE = "#fbfbfd"
DATA = "#3552c8"  # série principale (bleu « piste »)
HIGHLIGHT = "#c8620a"  # mise en avant (safran) — paire validée daltonisme, contraste ≥ 3:1


def use_style() -> None:
    """Applique le style graphique du projet à matplotlib."""
    mpl.rcParams.update(
        {
            "figure.dpi": 110,
            "savefig.dpi": 150,
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "axes.edgecolor": AXIS,
            "axes.labelcolor": INK_2,
            "axes.titlecolor": INK,
            "axes.titlesize": 12,
            "axes.titleweight": "semibold",
            "axes.titlelocation": "left",
            "axes.titlepad": 12,
            "axes.labelsize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.frameon": False,
            "legend.fontsize": 9,
            "font.family": "DejaVu Sans",
        }
    )


def rupees(x: float, _pos: int | None = None) -> str:
    """Format d'axe : 12 000 ₹ (espace fine comme séparateur de milliers)."""
    return f"{x:,.0f}".replace(",", " ") + " ₹"


def thousands(x: float, _pos: int | None = None) -> str:
    return f"{x:,.0f}".replace(",", " ")


def price_boxes(
    frame: pd.DataFrame,
    by: str,
    ax: Axes,
    order: Sequence | None = None,
    labels: dict | None = None,
    title: str = "",
) -> Axes:
    """Boîtes horizontales des prix par groupe : déciles 1–9 (moustaches), quartiles, médiane."""
    groups = frame.groupby(by, observed=True)["price"]
    keys = list(order) if order is not None else list(groups.median().sort_values().index)
    for i, key in enumerate(keys):
        prices = groups.get_group(key)
        p10, q1, med, q3, p90 = prices.quantile([0.1, 0.25, 0.5, 0.75, 0.9])
        ax.plot([p10, p90], [i, i], color=AXIS, lw=1.5, solid_capstyle="round", zorder=1)
        ax.barh(i, q3 - q1, left=q1, height=0.5, color=DATA, alpha=0.22, zorder=2)
        ax.plot([med, med], [i - 0.25, i + 0.25], color=DATA, lw=2.5, zorder=3)
        ax.text(
            p90,
            i,
            f"  {len(prices):,} vols".replace(",", " "),
            va="center",
            fontsize=8,
            color=MUTED,
        )
    ax.set_yticks(range(len(keys)), [labels.get(k, k) if labels else k for k in keys])
    ax.invert_yaxis()
    ax.xaxis.set_major_locator(MaxNLocator(5))
    ax.xaxis.set_major_formatter(FuncFormatter(thousands))
    ax.set_xlabel("prix (₹)")
    ax.grid(axis="y", visible=False)
    ax.set_title(title)
    ax.margins(x=0.14)
    return ax


def median_price_by_date(frame: pd.DataFrame, ax: Axes, title: str = "") -> Axes:
    """Prix médian (et intervalle interquartile) par date de voyage."""
    stats = frame.groupby("journey_date")["price"].agg(
        q1=lambda s: s.quantile(0.25), median="median", q3=lambda s: s.quantile(0.75)
    )
    ax.fill_between(
        stats.index,
        stats["q1"],
        stats["q3"],
        color=DATA,
        alpha=0.15,
        lw=0,
        label="50 % des vols (quartiles)",
    )
    ax.plot(stats.index, stats["median"], color=DATA, lw=2, marker="o", ms=3.5, label="prix médian")
    ax.yaxis.set_major_formatter(FuncFormatter(rupees))
    ax.set_title(title)
    ax.legend(loc="upper right")
    return ax


def model_bars(table: pd.DataFrame, ax: Axes, metric: str = "MAE", highlight: str = "") -> Axes:
    """Barres horizontales d'une métrique de validation croisée (± écart-type)."""
    ordered = table.sort_values(metric, ascending=metric != "R2")
    colors = [HIGHLIGHT if name == highlight else DATA for name in ordered.index]
    err = ordered.get(f"{metric} (é.-t.)")
    ax.barh(
        ordered.index,
        ordered[metric],
        xerr=err,
        color=colors,
        height=0.5,
        error_kw={"ecolor": INK_2, "elinewidth": 1, "capsize": 3},
    )
    spread = err if err is not None else pd.Series(0.0, index=ordered.index)
    for i, (value, sd) in enumerate(zip(ordered[metric], spread, strict=True)):
        text = f"{value:.3f}" if metric == "R2" else thousands(value) + " ₹"
        ax.text(value + sd, i, "  " + text, va="center", fontsize=9, color=INK_2)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    if metric != "R2":
        ax.xaxis.set_major_formatter(FuncFormatter(thousands))
    ax.margins(x=0.18)
    return ax


def predicted_vs_actual(
    y_true: np.ndarray, y_pred: np.ndarray, ax: Axes, interval: tuple[float, float] | None = None
) -> Axes:
    """Prix prédit contre prix réel (échelles log), avec la diagonale et l'intervalle à 80 %."""
    ax.hexbin(
        y_true,
        y_pred,
        gridsize=45,
        xscale="log",
        yscale="log",
        mincnt=1,
        cmap="Blues",
        linewidths=0.2,
        edgecolors=SURFACE,
    )
    lims = np.array([min(y_true.min(), y_pred.min()), max(y_true.max(), y_pred.max())])
    ax.plot(lims, lims, color=INK, lw=1, label="prédiction parfaite")
    if interval:
        low, high = interval
        ax.plot(lims, lims * low, color=HIGHLIGHT, lw=1, ls=(0, (4, 3)))
        ax.plot(
            lims,
            lims * high,
            color=HIGHLIGHT,
            lw=1,
            ls=(0, (4, 3)),
            label=f"intervalle à 80 % ({fr_pct(low - 1, 0, True)} / {fr_pct(high - 1, 0, True)})",
        )
    ax.set_xlabel("prix réel (₹, échelle log)")
    ax.set_ylabel("prix prédit (₹, échelle log)")
    ticks = [2000, 3000, 5000, 10000, 20000, 30000, 50000]
    for axis in (ax.xaxis, ax.yaxis):
        axis.set_major_locator(FixedLocator(ticks))
        axis.set_major_formatter(FuncFormatter(thousands))
        axis.set_minor_formatter(NullFormatter())
    ax.legend(loc="upper left")
    return ax


def importance_bars(importances: pd.DataFrame, ax: Axes, labels: dict, top: int = 10) -> Axes:
    """Importance par permutation : hausse de la MAE quand on brouille la variable."""
    data = importances.head(top).iloc[::-1]
    ax.barh(
        [labels.get(v, v) for v in data["variable"]],
        data["hausse MAE (₹)"],
        xerr=data["é.-t."],
        color=DATA,
        height=0.55,
        error_kw={"ecolor": INK_2, "elinewidth": 1, "capsize": 2},
    )
    ax.grid(axis="y", visible=False)
    ax.xaxis.set_major_formatter(FuncFormatter(rupees))
    ax.set_xlabel("hausse de la MAE quand la variable est brouillée")
    return ax


def new_figure(width: float = 9, height: float = 4.2, **kwargs):
    """Figure aux dimensions du projet (lisibles sur GitHub)."""
    return plt.subplots(figsize=(width, height), layout="constrained", **kwargs)


def save(fig: Figure, name: str) -> Path:
    """Enregistre une figure dans `assets/figures/` (PNG), pour le README."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / f"{name}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=SURFACE)
    return path
