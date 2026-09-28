# Data sources

Two public sources, both downloaded by `make data` from their original
locations. Neither is committed to this repository (see
[Licensing](#licensing)).

## StatsBomb Open Data (primary)

Event data for every match: each pass, carry, shot, pressure, duel and
substitution, with pitch coordinates, outcomes, the players involved and
StatsBomb's expected-goals (xG) value on every shot. Lineups give each
player's spells on the pitch and positions.

| | |
|---|---|
| Repository | [statsbomb/open-data](https://github.com/statsbomb/open-data) |
| Pinned commit | `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb` |
| Used | La Liga 2004/05-2020/21 (866 matches: 524 Barcelona league matches across 17 seasons, plus all 380 matches of 2015/16) and the 2009, 2011 and 2015 Champions League finals |
| Events | 3,140,830 |
| Players | 2,413 (153 for Barcelona) |
| 360 freeze frames | 35 matches of 2020/21, optional (`make data-360`) |

**Why this source.** It is the only free, legal event dataset with enough
consecutive Barcelona seasons to study trends, build rolling form and
backtest predictions honestly, and it has professional xG. The Wyscout
public dataset (Pappalardo et al., 2019) could be redistributed, but it
covers a single season and has no xG
([D-001](decision-log.md#d-001---primary-dataset-statsbomb-open-data)).

**Coverage caveats.** Outside 2015/16, StatsBomb only has matches that
Barcelona played, and the early seasons are partial and skewed towards
matches Lionel Messi played (2004/05 has 7 of 38 league matches). Coverage
is at least 82% of the league season from 2008/09. There are no cup or
European matches apart from the three finals. `reports/data_coverage.md` has
the season-by-season table.

## football-data.co.uk (secondary)

La Liga (division `SP1`) results for 1995/96-2020/21: 10,044 matches with
full- and half-time scores, shots, shots on target, corners, fouls and cards
(from 2005/06), and bookmaker odds (Pinnacle closing odds from 2012/13).

**Why this source.** StatsBomb alone cannot say how strong an opponent was
or what form it was in: outside 2015/16 opponents only appear against
Barcelona. The complete league schedule gives Elo ratings and results-based
form for every club, nine seasons of Elo history before the first StatsBomb
match, and a training set of every league fixture rather than Barcelona's
alone. Bookmaker odds are an external benchmark for the models and are never
used as features
([D-002](decision-log.md#d-002---secondary-dataset-football-datacouk-la-liga-results)).

## How the two are joined

StatsBomb and football-data name clubs differently ("Athletic Club" vs
"Ath Bilbao"). A crosswalk was derived by matching all 866 StatsBomb league
matches to football-data on date and score (every match found, none
ambiguous) and is stored as reference data in
`src/barca/data/reference/teams.csv`, with display names and three-letter
codes. Validation rule M05 re-checks the join on every build: date, teams
and score must agree for every league match.

## Reproducibility

- StatsBomb is fetched from a fixed commit, so every rebuild sees
  byte-identical inputs.
- `data/raw/MANIFEST.json` records a SHA-256 checksum of every downloaded
  file's content after each download. football-data files are not
  versioned upstream, so this is how a changed file becomes visible.
- Raw JSON is stored gzip-compressed (297 MB instead of about 3 GB), with no
  timestamp in the gzip header, and checksums are taken on the decompressed
  content. Two downloads of the same data therefore have identical
  checksums.
- `barca fetch --sample N` downloads only the N most recent Barcelona
  matches, which is what CI uses.

## Licensing

The StatsBomb user agreement does not allow the data to be redistributed
(clause 1.2.1), so `data/` is git-ignored and the repository contains code,
analysis and figures only. Publishing analysis is allowed with attribution
and the StatsBomb logo (clause 1.4), which the README and every page of the
web app show. football-data.co.uk files are free to download from the
site; they are not redistributed here either.

The source code is not open source: it is © Manshul Budholiya, all rights
reserved (see `LICENSE`). That licence does not cover the data.

This is a personal, non-commercial project. It is not affiliated with,
endorsed by or connected to FC Barcelona, StatsBomb or football-data.co.uk.
