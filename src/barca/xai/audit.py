"""XAI as model auditing: flag explanations that could only come from leakage."""

from __future__ import annotations

import re
from collections.abc import Iterable

# Columns that exist only after (or during) the match being predicted.
POST_MATCH_PATTERNS = [
    r"^(home|away)_(goals|goals_ht|shots|sot|corners|fouls|yellow|red)$", r"^result$", r"_post$",
    r"^mkt_", r"^(barca|opp)_goals$", r"^xg$|^xga$|_xg_match$",
]


def suspicious(features: Iterable[str]) -> list[str]:
    pats = [re.compile(p) for p in POST_MATCH_PATTERNS]
    return [f for f in features if any(p.search(f) for p in pats)]


def check_top_features(importance: dict[str, float], k: int = 15) -> list[str]:
    """Return any post-match column among the ``k`` most important features (empty list = pass)."""
    top = sorted(importance, key=lambda f: -abs(importance[f]))[:k]
    return suspicious(top)
