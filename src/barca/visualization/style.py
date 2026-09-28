"""Shared figure style for notebooks and reports.

Colour roles, not raw colours, are used throughout the project:

* ``BARCA`` / ``OPPONENT`` / ``THIRD`` - categorical identity (validated for
  colour-vision deficiency on the light surface: worst adjacent CVD dE 22.6).
  The gold third slot is below 3:1 contrast on white, so wherever it is used
  the series is also labelled directly.
* ``RESULT_COLOURS`` - win/draw/loss are states, so they use the status
  palette and are always shown together with the W/D/L letter.
* ``HEAT`` - a single-hue sequential ramp for magnitudes (heatmaps).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from cycler import cycler
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap

from barca import config

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

BARCA = "#a50044"
OPPONENT = "#2a78d6"
THIRD = "#eda100"
NEUTRAL = "#b9b8b1"

RESULT_COLOURS = {"W": "#0ca30c", "D": "#898781", "L": "#d03b3b"}

HEAT = LinearSegmentedColormap.from_list(
    "barca_heat", [SURFACE, "#f3c6d6", "#d9588a", BARCA, "#4f0021"]
)
HEAT_BLUE = LinearSegmentedColormap.from_list(
    "blue_heat", [SURFACE, "#cde2fb", "#6da7ec", "#2a78d6", "#104281"]
)
DIVERGING = LinearSegmentedColormap.from_list(
    "blue_red", ["#104281", "#6da7ec", "#f0efec", "#e87b7b", "#a01f1f"]
)


FONTS = ["Inter", "Helvetica Neue", "Arial", "DejaVu Sans"]


def _installed_fonts() -> list[str]:
    """The preferred fonts that exist on this machine (DejaVu Sans ships with matplotlib)."""
    available = {f.name for f in font_manager.fontManager.ttflist}
    return [f for f in FONTS if f in available] or ["DejaVu Sans"]


def apply() -> None:
    mpl.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "figure.dpi": 110,
            "savefig.dpi": 160,
            "savefig.bbox": "tight",
            "font.family": _installed_fonts(),
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.titlepad": 10,
            "axes.labelsize": 10,
            "axes.labelcolor": INK_2,
            "axes.edgecolor": AXIS,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "grid.linestyle": "-",
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelcolor": INK_2,
            "ytick.labelcolor": INK_2,
            "text.color": INK,
            "legend.frameon": False,
            "legend.fontsize": 9,
            "lines.linewidth": 2,
            "lines.markersize": 6,
            "axes.prop_cycle": cycler(color=[BARCA, OPPONENT, THIRD, "#1baf7a", "#4a3aa7"]),
        }
    )


def savefig(fig: plt.Figure, name: str, directory: Path | None = None) -> Path:
    directory = directory or config.FIGURES
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.png"
    fig.savefig(path)
    return path


def caption(ax: plt.Axes, text: str) -> None:
    """Small source/method note below the whole figure (outside the axes)."""
    ax.figure.text(0.01, -0.01, text, fontsize=7.5, color=MUTED, ha="left", va="top")


STATSBOMB_CREDIT = "Data: StatsBomb Open Data"
