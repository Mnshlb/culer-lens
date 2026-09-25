"""Where the data comes from and which slice of it the project uses.

StatsBomb Open Data is pinned to a single commit so that every rebuild sees
byte-identical inputs. football-data.co.uk files are not versioned upstream, so
their checksums are recorded in the raw manifest instead.
"""

from __future__ import annotations

from dataclasses import dataclass

STATSBOMB_REPO = "statsbomb/open-data"
STATSBOMB_COMMIT = "4b73468fc5b0f1950f9f66fada70ad3a4f9327cb"
STATSBOMB_BASE_URL = f"https://raw.githubusercontent.com/{STATSBOMB_REPO}/{STATSBOMB_COMMIT}/data"

LA_LIGA = 11
CHAMPIONS_LEAGUE = 16
COPA_DEL_REY = 87
CATALOGUE_COMPETITIONS = (LA_LIGA, CHAMPIONS_LEAGUE, COPA_DEL_REY)

BARCELONA = "Barcelona"

# The contiguous Barcelona era in the open data. The 1970s/80s single matches
# are kept in the catalogue (they show up in the coverage report) but have no
# neighbours to compute form from, so their events are not downloaded.
FIRST_SEASON = "2004/2005"
LAST_SEASON = "2020/2021"

FOOTBALL_DATA_BASE_URL = "https://www.football-data.co.uk/mmz4281"
FOOTBALL_DATA_DIVISION = "SP1"
# Results from 1995/96 give the Elo ratings nine seasons of burn-in before the
# first StatsBomb match.
FOOTBALL_DATA_FIRST_START_YEAR = 1995
FOOTBALL_DATA_LAST_START_YEAR = 2020


@dataclass(frozen=True)
class SeasonCode:
    start_year: int

    @property
    def label(self) -> str:
        return f"{self.start_year}/{self.start_year + 1}"

    @property
    def football_data_code(self) -> str:
        return f"{self.start_year % 100:02d}{(self.start_year + 1) % 100:02d}"


def season_start_year(label: str) -> int:
    """'2015/2016' -> 2015."""
    return int(label.split("/")[0])


def in_scope_season(label: str) -> bool:
    return (
        season_start_year(FIRST_SEASON)
        <= season_start_year(label)
        <= season_start_year(LAST_SEASON)
    )


def football_data_seasons() -> list[SeasonCode]:
    return [
        SeasonCode(y)
        for y in range(FOOTBALL_DATA_FIRST_START_YEAR, FOOTBALL_DATA_LAST_START_YEAR + 1)
    ]
