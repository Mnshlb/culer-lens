from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from barca.data import normalize


@pytest.mark.parametrize(
    ("raw", "seconds"), [("45:00", 2700.0), ("00:00:04.227", 4.227), ("01:02:03.500", 3723.5)]
)
def test_clock_to_seconds(raw: str, seconds: float) -> None:
    assert pl.select(normalize.clock_to_seconds(pl.lit(raw))).item() == pytest.approx(seconds)


def test_football_data_dates_switch_format_by_length() -> None:
    # parsing '16/10/04' with %Y would silently give the year 0004
    out = (
        pl.select(normalize.football_data_date(pl.Series(["16/10/04", "17/08/2018"])))
        .to_series()
        .to_list()
    )
    assert out == [date(2004, 10, 16), date(2018, 8, 17)]


def test_team_names_are_canonical() -> None:
    names = pl.select(
        normalize.football_data_team_name(pl.Series(["Villareal", "Ath Bilbao", "Espanol"]))
    ).to_series()
    assert names.to_list() == ["Villarreal", "Athletic Club", "Espanyol"]


def test_minutes_count_stoppage_time_and_map_the_second_half_clock() -> None:
    # first half ran to 47:00 (2 min stoppage), second half 45:00 -> 94:00
    bounds = pl.DataFrame(
        {
            "match_id": [1, 1],
            "period": [1, 2],
            "end_s": [2820.0, 5640.0],
            "start_s": [0.0, 2700.0],
            "duration_s": [2820.0, 2940.0],
            "elapsed_before_s": [0.0, 2820.0],
        },
        schema_overrides={"period": pl.Int8},
    )
    positions = pl.DataFrame(
        {
            "match_id": [1, 1, 1],
            "team_id": [1, 1, 1],
            "player_id": [10, 11, 12],
            "spell": [0, 0, 0],
            "position_id": [1, 2, 2],
            "position": ["Goalkeeper", "Right Back", "Right Back"],
            "from_clock": ["00:00", "00:00", "60:00"],
            "to_clock": [None, "60:00", None],
            "from_period": [1, 1, 2],
            "to_period": [None, 2, None],
            "start_reason": ["Starting XI", "Starting XI", "Substitution - On (Tactical)"],
            "end_reason": ["Final Whistle", "Substitution - Off (Tactical)", "Final Whistle"],
        },
        schema_overrides={"from_period": pl.Int8, "to_period": pl.Int8},
    )
    m = normalize.player_minutes(positions, bounds).sort("player_id")
    full, subbed_off, subbed_on = m["minutes"].to_list()
    assert full == pytest.approx(96.0)  # 47 + 49
    assert subbed_off == pytest.approx(62.0)  # 47 first half + 15 of the second
    assert subbed_off + subbed_on == pytest.approx(full)
    assert m["started"].to_list() == [True, True, False]
