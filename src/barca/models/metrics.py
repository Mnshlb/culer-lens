"""Scoring rules for three-way outcome probabilities.

Classes are always ordered from the reference side's perspective:
``[win, draw, loss]`` (home win / draw / away win for league fixtures). The
order matters for the ranked probability score, which treats the outcomes as
ordinal.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import confusion_matrix, f1_score

EPS = 1e-12


def one_hot(y: np.ndarray, k: int = 3) -> np.ndarray:
    out = np.zeros((len(y), k))
    out[np.arange(len(y)), y] = 1
    return out


def log_loss(y: np.ndarray, p: np.ndarray) -> float:
    return float(-np.mean(np.log(np.clip(p[np.arange(len(y)), y], EPS, 1))))


def brier(y: np.ndarray, p: np.ndarray) -> float:
    """Multi-class Brier score: mean squared distance to the outcome (0 best, 2 worst)."""
    return float(np.mean(np.sum((p - one_hot(y, p.shape[1])) ** 2, axis=1)))


def rps(y: np.ndarray, p: np.ndarray) -> float:
    """Ranked probability score for ordered outcomes (0 best)."""
    cum_p = np.cumsum(p, axis=1)[:, :-1]
    cum_o = np.cumsum(one_hot(y, p.shape[1]), axis=1)[:, :-1]
    return float(np.mean(np.sum((cum_p - cum_o) ** 2, axis=1) / (p.shape[1] - 1)))


def accuracy(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean(np.argmax(p, axis=1) == y))


def macro_f1(y: np.ndarray, p: np.ndarray) -> float:
    return float(
        f1_score(y, np.argmax(p, axis=1), average="macro", labels=[0, 1, 2], zero_division=0)
    )


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    """Expected calibration error over all three classes (one-vs-rest)."""
    total = 0.0
    edges = np.linspace(0, 1, bins + 1)
    for k in range(p.shape[1]):
        pk, ok = p[:, k], (y == k).astype(float)
        idx = np.clip(np.digitize(pk, edges) - 1, 0, bins - 1)
        for b in range(bins):
            m = idx == b
            if m.any():
                total += m.sum() * abs(pk[m].mean() - ok[m].mean())
    return float(total / (len(y) * p.shape[1]))


def summary(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    return {
        "n": len(y),
        "log_loss": log_loss(y, p),
        "brier": brier(y, p),
        "rps": rps(y, p),
        "accuracy": accuracy(y, p),
        "macro_f1": macro_f1(y, p),
        "ece": ece(y, p),
    }


def confusion(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    return confusion_matrix(y, np.argmax(p, axis=1), labels=[0, 1, 2])


def reliability(y: np.ndarray, p: np.ndarray, cls: int, bins: int = 10) -> list[dict[str, float]]:
    """Mean predicted vs observed frequency per probability bin, for one class."""
    pk, ok = p[:, cls], (y == cls).astype(float)
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(pk, edges) - 1, 0, bins - 1)
    out = []
    for b in range(bins):
        m = idx == b
        if m.sum() >= 5:
            out.append(
                {
                    "bin": b,
                    "predicted": float(pk[m].mean()),
                    "observed": float(ok[m].mean()),
                    "n": int(m.sum()),
                }
            )
    return out
