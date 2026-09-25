"""Human-readable names for features, used by explanations in notebooks and the app."""

from __future__ import annotations

import re

_STATS = {
    "points": "points per game", "goals": "goals scored", "goals_against": "goals conceded",
    "goal_diff": "goal difference", "shots": "shots", "shots_against": "shots conceded", "sot": "shots on target",
    "sot_against": "shots on target conceded", "corners": "corners", "corners_against": "corners conceded",
}
_FIXED = {
    "elo_diff": "Elo gap", "elo_expected": "Elo expectation (incl. home advantage)",
    "form_diff_5": "form gap, last 5", "form_diff_10": "form gap, last 10", "strength_diff_10": "goal-difference gap, last 10",
    "sot_strength_diff_10": "shots-on-target gap, last 10", "attack_matchup_10": "attack vs opponent defence, last 10",
    "defence_matchup_10": "defence vs opponent attack, last 10", "ppg_std_diff": "season points-per-game gap",
    "rest_diff": "rest-days gap", "is_home": "home advantage",
}


_SIGNED = {"elo_diff", "form_diff_5", "form_diff_10", "strength_diff_10", "sot_strength_diff_10", "ppg_std_diff",
           "rest_diff"}


def side_of(feature: str) -> str | None:
    for prefix, side in (("h_", "home"), ("a_", "away"), ("barca_", "barca"), ("opp_", "opponent")):
        if feature.startswith(prefix):
            return side
    return None


def describe(feature: str) -> str:
    if feature in _FIXED:
        return _FIXED[feature]
    side = side_of(feature)
    core = feature.split("_", 1)[1] if side else feature
    if core == "elo":
        text = "Elo rating"
    elif core.startswith("h2h_"):
        text = "head-to-head " + ("points" if "points" in core else "goal difference") + ", last 4 meetings"
    elif core.startswith("venue_"):
        text = ("points" if "points" in core else "goal difference") + " at this venue, last 5"
    elif core.endswith("_ewm"):
        text = _STATS.get(core[:-4], core[:-4]) + " (recent, weighted)"
    elif core.endswith("_std"):
        text = _STATS.get(core[:-4], core[:-4]) + " this season"
    elif core == "matches_played":
        text = "matches played this season"
    elif core == "days_rest":
        text = "days of rest"
    else:
        m = re.match(r"(.+)_(\d+)$", core)
        text = f"{_STATS.get(m.group(1), m.group(1).replace('_', ' '))}, last {m.group(2)}" if m else core.replace("_", " ")
    return text


def fixture_label(feature: str) -> str:
    """Label from the fixture's perspective: 'Home ...' / 'Away ...' for side-specific features."""
    side = side_of(feature)
    if side in ("home", "away"):
        return f"{side.title()} {describe(feature)}"
    return describe(feature) + (" (home − away)" if feature in _SIGNED else "")


def barca_label(feature: str, barca_home: bool) -> str:
    """Label a home/away-perspective feature from Barcelona's point of view."""
    side = side_of(feature)
    if side in ("home", "away"):
        is_barca = (side == "home") == barca_home
        return f"{'Barcelona' if is_barca else 'Opponent'} {describe(feature)}"
    return describe(feature)


def barca_view(feature: str, value: float | None, barca_home: bool) -> tuple[str, float | None]:
    """Label and value of a home-perspective feature as seen from Barcelona.

    Differences are home minus away, so their sign flips when Barcelona are
    away; the Elo expectation becomes Barcelona's; matchup terms swap sides.
    """
    if feature in _SIGNED:
        return describe(feature) + " (Barcelona − opponent)", (value if barca_home or value is None else -value)
    if feature == "elo_expected":
        v = value if barca_home or value is None else 1 - value
        return "Barcelona's Elo expectation (incl. home advantage)", v
    if feature == "attack_matchup_10":
        return ("Barcelona attack vs opponent defence, last 10" if barca_home
                else "Opponent attack vs Barcelona defence, last 10"), value
    if feature == "defence_matchup_10":
        return ("Opponent attack vs Barcelona defence, last 10" if barca_home
                else "Barcelona attack vs opponent defence, last 10"), value
    return barca_label(feature, barca_home), value


GROUPS = {
    "Team strength (Elo)": re.compile(r"^(h_elo|a_elo|elo_diff|elo_expected)$"),
    "Recent form": re.compile(r"^(h_|a_)(points|goal_diff|goals|goals_against)_(3|5|10|ewm)$|^form_diff_|^strength_diff_"),
    "Shots and chances": re.compile(r"^(h_|a_)(shots|shots_against|sot|sot_against|corners|corners_against)_|^sot_strength|_matchup_"),
    "Venue form": re.compile(r"^(h_|a_)venue_"),
    "Season so far": re.compile(r"^(h_|a_)(points_std|goal_diff_std|matches_played)$|^ppg_std_diff$"),
    "Head-to-head": re.compile(r"h2h_"),
    "Rest": re.compile(r"days_rest|rest_diff"),
}


def group_of(feature: str) -> str:
    for name, pattern in GROUPS.items():
        if pattern.search(feature):
            return name
    return "Other"
