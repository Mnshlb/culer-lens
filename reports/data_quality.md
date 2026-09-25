# Data quality report

| Rule | Table | Check | Severity | Violations | Tolerance | Status |
|---|---|---|---|---|---|---|
| E01 | events | event ids are unique | error | 0 | 0 | pass |
| E02 | events | event index runs 1..n within every match | error | 0 | 0 | pass |
| E03 | events | period is 1-5 | error | 0 | 0 | pass |
| E04 | events | minute/second are valid for the period | error | 0 | 0 | pass |
| E05 | events | periods never go backwards in index order | warning | 1 | 5 | pass |
| E06 | events | timestamps rarely go backwards within a period (related events can be recorded out of order) | warning | 314 | 1000 | pass |
| E07 | events | locations lie on the 120 x 80 pitch | error | 0 | 0 | pass |
| E08 | events | every shot has an xG in (0, 1) | error | 0 | 0 | pass |
| E09 | events | every shot has an outcome, a start and an end location | error | 0 | 0 | pass |
| E10 | events | every pass has a start and an end location | error | 0 | 0 | pass |
| E11 | events | every carry has an end location | error | 0 | 0 | pass |
| E12 | events | completed passes name a recipient | warning | 0 | 0 | pass |
| E13 | events | substitutions name a replacement from the same squad | error | 0 | 0 | pass |
| E14 | events | on-ball events have a player and a team | error | 0 | 0 | pass |
| E15 | events | event team is one of the two teams in the match | error | 0 | 0 | pass |
| E16 | events | every event player is in that team's matchday lineup | error | 0 | 0 | pass |
| E17 | events | related_events point to events in the same match | error | 0 | 0 | pass |
| E18 | events | shot key-pass ids point to a pass in the same match | error | 0 | 0 | pass |
| E19 | events | event types come from the known vocabulary | error | 0 | 0 | pass |
| E20 | events | outcomes come from the known vocabulary for their type | warning | 0 | 0 | pass |
| E21 | events | one Starting XI per team per match, with 11 players | error | 0 | 0 | pass |
| E22 | events | goals reconstructed from events equal the official score | error | 0 | 0 | pass |
| M01 | matches | match ids are unique | error | 0 | 0 | pass |
| M02 | matches | home and away teams differ | error | 0 | 0 | pass |
| M03 | matches | scores are non-negative | error | 0 | 0 | pass |
| M04 | matches | match date falls inside its season | error | 0 | 0 | pass |
| M05 | matches | every league match reconciles with football-data (date, teams, score) | error | 0 | 0 | pass |
| L01 | appearances | minutes played lie between 0 and match length | error | 0 | 0 | pass |
| L02 | appearances | exactly 11 starters per team per match | error | 0 | 0 | pass |
| L03 | appearances | a player belongs to one team per match | error | 0 | 0 | pass |
| L04 | appearances | team minutes are consistent with 9-11 players on the pitch | warning | 12 | 15 | pass |
| R01 | results | one fixture per (season, home, away) | error | 0 | 0 | pass |
| R02 | results | every season is a complete double round robin | error | 0 | 0 | pass |
| R03 | results | half-time goals never exceed full-time goals | error | 0 | 0 | pass |
| R04 | results | shots are never fewer than shots on target | error | 0 | 0 | pass |
| R05 | results | bookmaker odds are above 1.0 | error | 0 | 0 | pass |
| R06 | results | every fixture has a date and a full-time score | error | 0 | 0 | pass |

## Samples of violating rows

**E05** (1 rows)

```
[
 {
  "match_id": 3825848,
  "index": 2590,
  "period": 1,
  "type": "Ball Receipt*"
 }
]
```

**E06** (314 rows)

```
[
 {
  "match_id": 9575,
  "index": 2082,
  "period": 1,
  "timestamp": "00:00:04.227"
 },
 {
  "match_id": 9581,
  "index": 1863,
  "period": 1,
  "timestamp": "00:00:01.159"
 },
 {
  "match_id": 9581,
  "index": 3904,
  "period": 2,
  "timestamp": "00:47:59.575"
 },
 {
  "match_id": 9636,
  "index": 2073,
  "period": 1,
  "timestamp": "00:00:01.342"
 },
 {
  "match_id": 9642,
  "index": 2072,
  "period": 1,
  "timestamp": "00:00:00.239"
 }
]
```

**L04** (12 rows)

```
[
 {
  "match_id": 69144,
  "team_id": 212,
  "team_minutes": 1094.8666666666666,
  "match_minutes": 95.38333333333333
 },
 {
  "match_id": 3825565,
  "team_id": 214,
  "team_minutes": 1051.0833333333333,
  "match_minutes": 94.01666666666667
 },
 {
  "match_id": 3825729,
  "team_id": 1041,
  "team_minutes": 1088.3499999999997,
  "match_minutes": 94.05
 },
 {
  "match_id": 3825707,
  "team_id": 208,
  "team_minutes": 1098.5333333333333,
  "match_minutes": 95.13333333333333
 },
 {
  "match_id": 69222,
  "team_id": 1220,
  "team_minutes": 1028.6,
  "match_minutes": 93.41666666666667
 }
]
```

