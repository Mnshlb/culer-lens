"""Pitch drawing helpers built on mplsoccer (StatsBomb 120 x 80 coordinates)."""

from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from mplsoccer import Pitch, VerticalPitch

from barca.visualization import style

PITCH_KW: dict[str, Any] = {
    "pitch_type": "statsbomb",
    "pitch_color": style.SURFACE,
    "line_color": "#b9b8b1",
    "linewidth": 1,
    "goal_type": "box",
    "corner_arcs": True,
}


def pitch(**kwargs: Any) -> Pitch:
    return Pitch(**{**PITCH_KW, **kwargs})


def vertical_pitch(**kwargs: Any) -> VerticalPitch:
    return VerticalPitch(**{**PITCH_KW, **kwargs})


def heatmap(
    ax: plt.Axes,
    x: np.ndarray,
    y: np.ndarray,
    *,
    bins: tuple[int, int] = (24, 16),
    cmap: Any = None,
    title: str | None = None,
    normalise: bool = True,
) -> Any:
    """Binned event heatmap with light Gaussian smoothing."""
    from scipy.ndimage import gaussian_filter

    p = pitch()
    p.draw(ax=ax)
    stats = p.bin_statistic(x, y, statistic="count", bins=bins)
    stats["statistic"] = gaussian_filter(stats["statistic"], 0.9)
    if normalise and stats["statistic"].sum() > 0:
        stats["statistic"] = stats["statistic"] / stats["statistic"].sum()
    mesh = p.heatmap(stats, ax=ax, cmap=cmap or style.HEAT, edgecolors=style.SURFACE, linewidth=0.3)
    if title:
        ax.set_title(title)
    return mesh
