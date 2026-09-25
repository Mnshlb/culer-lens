"""Football metric definitions as reusable Polars expressions.

Every metric in the project (team stats, player stats, heatmap filters) is
built from these predicates, so a definition changes in exactly one place.
Coordinates are StatsBomb's 120 x 80 yards, attacking left to right from the
perspective of the team performing the event.

Definitions follow common public conventions where one exists and are
documented in docs/data-dictionary.md.
"""

from __future__ import annotations

import polars as pl

PITCH_X = 120.0
PITCH_Y = 80.0
BOX_X = 102.0
BOX_Y_MIN, BOX_Y_MAX = 18.0, 62.0
FINAL_THIRD_X = 80.0
MIDDLE_THIRD_X = 40.0
PROGRESSION_MIN_X = 48.0  # progressive actions must start outside the defending 40%
PROGRESSION_GAIN = 10.0  # yards gained towards the opponent's goal line

T = pl.col("type")
SUB = pl.col("subtype")
OUT = pl.col("outcome")
X, Y, EX, EY = pl.col("x"), pl.col("y"), pl.col("end_x"), pl.col("end_y")

SET_PIECE_PASS_TYPES = ["Corner", "Free Kick", "Throw-in", "Goal Kick", "Kick Off"]
WON_OUTCOMES = ["Won", "Success", "Success In Play", "Success Out"]
ON_TARGET_OUTCOMES = ["Goal", "Saved", "Saved to Post"]


def in_box(x: pl.Expr, y: pl.Expr) -> pl.Expr:
    return (x >= BOX_X) & (y >= BOX_Y_MIN) & (y <= BOX_Y_MAX)


# Passing ----------------------------------------------------------------------------
PASS = T == "Pass"
# StatsBomb leaves the outcome empty for completed passes.
PASS_COMPLETE = PASS & OUT.is_null()
SET_PIECE_PASS = PASS & SUB.is_in(SET_PIECE_PASS_TYPES).fill_null(False)
OPEN_PLAY_PASS = PASS & ~SUB.is_in(SET_PIECE_PASS_TYPES).fill_null(False)
PROGRESSIVE_PASS = (
    PASS_COMPLETE
    & OPEN_PLAY_PASS
    & (X >= PROGRESSION_MIN_X)
    & (((EX - X) >= PROGRESSION_GAIN) | (in_box(EX, EY) & ~in_box(X, Y)))
)
FINAL_THIRD_PASS = PASS_COMPLETE & (X < FINAL_THIRD_X) & (EX >= FINAL_THIRD_X)
BOX_PASS = (
    PASS_COMPLETE
    & in_box(EX, EY)
    & ~in_box(X, Y)
    & ~SUB.is_in(["Corner", "Free Kick"]).fill_null(False)
)
PASS_IN_FINAL_THIRD = PASS & (X >= FINAL_THIRD_X)
CROSS = PASS & pl.col("pass_cross").fill_null(False)
THROUGH_BALL = PASS & pl.col("pass_through_ball").fill_null(False)
SWITCH = PASS & pl.col("pass_switch").fill_null(False)
KEY_PASS = PASS & pl.col("pass_shot_assist").fill_null(False)
ASSIST = PASS & pl.col("pass_goal_assist").fill_null(False)
LONG_PASS = PASS & (pl.col("pass_length") >= 35)

# Carrying ---------------------------------------------------------------------------
CARRY = T == "Carry"
PROGRESSIVE_CARRY = (
    CARRY
    & (X >= PROGRESSION_MIN_X)
    & (((EX - X) >= PROGRESSION_GAIN) | (in_box(EX, EY) & ~in_box(X, Y)))
)
FINAL_THIRD_CARRY = CARRY & (X < FINAL_THIRD_X) & (EX >= FINAL_THIRD_X)
BOX_CARRY = CARRY & in_box(EX, EY) & ~in_box(X, Y)
DRIBBLE = T == "Dribble"
DRIBBLE_COMPLETE = DRIBBLE & (OUT == "Complete")

# Shooting ---------------------------------------------------------------------------
SHOT = T == "Shot"
PENALTY = SHOT & (SUB == "Penalty")
NON_PENALTY_SHOT = SHOT & (SUB != "Penalty")
SHOT_ON_TARGET = SHOT & OUT.is_in(ON_TARGET_OUTCOMES)
GOAL = SHOT & (OUT == "Goal")
NON_PENALTY_GOAL = GOAL & (SUB != "Penalty")
OPEN_PLAY_SHOT = (
    SHOT
    & (SUB == "Open Play")
    & ~pl.col("play_pattern").is_in(["From Corner", "From Free Kick", "From Throw In"])
)
SET_PIECE_SHOT = SHOT & (SUB != "Penalty") & ~OPEN_PLAY_SHOT
BIG_CHANCE = NON_PENALTY_SHOT & (pl.col("shot_xg") >= 0.3)
SHOT_IN_BOX = SHOT & in_box(X, Y)

# Defending --------------------------------------------------------------------------
PRESSURE = T == "Pressure"
COUNTERPRESS = PRESSURE & pl.col("counterpress").fill_null(False)
TACKLE = (T == "Duel") & (SUB == "Tackle")
TACKLE_WON = TACKLE & OUT.is_in(WON_OUTCOMES)
INTERCEPTION = T == "Interception"
INTERCEPTION_WON = INTERCEPTION & OUT.is_in(WON_OUTCOMES)
RECOVERY = (T == "Ball Recovery") & ~pl.col("recovery_failure").fill_null(False)
CLEARANCE = T == "Clearance"
BLOCK = T == "Block"
FOUL = T == "Foul Committed"
AERIAL_LOST = (T == "Duel") & (SUB == "Aerial Lost")
AERIAL_WON = pl.col("aerial_won").fill_null(False)
DRIBBLED_PAST = T == "Dribbled Past"
HIGH_RECOVERY = (RECOVERY | INTERCEPTION_WON) & (X >= FINAL_THIRD_X)
# Actions used for PPDA (Trainor's definition: tackles, interceptions, challenges, fouls).
PPDA_ACTION = TACKLE | INTERCEPTION | FOUL
DEFENSIVE_ACTION = PRESSURE | TACKLE | INTERCEPTION | RECOVERY | CLEARANCE | BLOCK | FOUL

# Possession loss / ball security -------------------------------------------------------
MISCONTROL = T == "Miscontrol"
DISPOSSESSED = T == "Dispossessed"
TURNOVER = MISCONTROL | DISPOSSESSED | (DRIBBLE & (OUT == "Incomplete"))

# Touches: any event in which the player has the ball at their feet.
TOUCH_TYPES = [
    "Pass",
    "Carry",
    "Dribble",
    "Shot",
    "Clearance",
    "Interception",
    "Ball Recovery",
    "Miscontrol",
    "Dispossessed",
    "Block",
    "Goal Keeper",
    "Shield",
    "50/50",
]
TOUCH = T.is_in(TOUCH_TYPES) | ((T == "Ball Receipt*") & OUT.is_null())
TOUCH_IN_BOX = TOUCH & in_box(X, Y)

# Heatmap action families (used by the spatial EDA and the API).
ACTION_FAMILIES: dict[str, pl.Expr] = {
    "all": T.is_in(
        [*TOUCH_TYPES, "Ball Receipt*", "Pressure", "Duel", "Foul Committed", "Foul Won"]
    ),
    "touches": TOUCH,
    "passes": PASS,
    "carries": CARRY,
    "attacking": SHOT | KEY_PASS | DRIBBLE | BOX_PASS | BOX_CARRY | TOUCH_IN_BOX,
    "defending": DEFENSIVE_ACTION | (T == "Duel"),
}
