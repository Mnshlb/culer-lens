# Data dictionary

What each table holds, the conventions every table follows, and how the
football metrics are defined. Column-level statistics (types, missingness,
ranges, outliers) for every table are in `reports/data_profile.md`, and the
90 model features are listed one by one in `reports/feature_catalog.md`.

## Conventions

| Topic | Convention |
|---|---|
| Coordinates | StatsBomb yards: x 0-120 along the pitch, y 0-80 across it. Every event is recorded in the acting team's frame, attacking towards x = 120; y = 0 is that team's left touchline. The API mirrors opponent events when both teams share one pitch. |
| Minutes | Elapsed playing time including stoppage time, derived from the event clock per period. A full match averages 94.3 minutes, so per-90 figures are slightly lower than on sites that cap matches at 90 ([D-010](decision-log.md#d-010---minutes-played-include-stoppage-time)). |
| Seasons | `season` is the label (`2015/2016`), `season_start` the first year (2015). |
| Perspective | Barcelona tables use `barca_` / `opp_` prefixes. League tables use `h_` / `a_` (home / away). Differences are always first side minus second side. |
| Identifiers | StatsBomb ids for matches, players and events in the pipeline; the application database uses its own integer keys and keeps `statsbomb_id` columns. `fixture_id` identifies a row of the football-data schedule, which covers every league match whether or not StatsBomb has it. |
| Nulls | Structural nulls are kept, never imputed. A null pass `outcome` means the pass was completed (StatsBomb's convention); a null `shot_xg` on a non-shot is expected. |

## Processed tables (`data/processed/`)

The cleaned, validated inputs to everything else.

| Table | Grain | Rows | Key columns |
|---|---|---|---|
| `matches` | match | 869 | `match_id`, `date`, `season`, `home`, `away`, scores, `is_barca`, `barca_venue`, `barca_result`, `barca_era` (head coach, from a tenure table, D-011) |
| `events` | event | 3,140,830 | `match_id`, `event_id`, `index`, `period`, `minute`, `second`, `type`, `subtype`, `outcome`, `team`, `player_id`, `x`, `y`, `end_x`, `end_y`, `shot_xg`, pass and shot flags, `possession`, `play_pattern`. Partitioned by season. |
| `appearances` | player × match | 29,711 | `minutes`, `started`, `start_position`, `position_group`, `position_family`, `on_minute`, `off_minute`, `end_reason`, cards |
| `positions` | position spell | 30,673 | every change of position within a match, with start and end clock |
| `tactics` | tactical event × player | 38,170 | formation and positions from Starting XI and Tactical Shift events |
| `period_bounds` | match × period | 1,738 | period start, end and duration, used to convert the clock to elapsed time |
| `results` | league fixture | 10,044 | football-data: scores, half-time scores, shots, shots on target, corners, fouls, cards, odds (Bet365, Pinnacle closing, market average) |
| `three_sixty`, `freeze_frames` | player in frame | 2.18 M / 266 k | 360 frames (2020/21) and shot freeze frames; EDA only |

**Position families** group StatsBomb's 25 positions into GK, CB, FB, MF,
AM (attacking midfielders and wingers) and FW. Ratings, heatmap comparisons
and lineup eligibility use them.

## Feature store (`data/features/`)

| Table | Grain | Rows | What it is |
|---|---|---|---|
| `team_match` | team × match | 1,738 | per-match team statistics from events, each row carrying the opponent's figures (`opp_`) |
| `player_match` | player × match | 24,234 | per-match player statistics from events, with minutes and positions |
| `team_form` | team × league fixture | 20,088 | rolling results-based form for every club, strictly before each fixture |
| `elo` | league fixture | 10,044 | pre-match Elo of both clubs, expected home score, post-match ratings |
| `event_form` | team × fixture | 1,718 | rolling StatsBomb-based form (xG, chances, pressing, progression) with coverage counts |
| `fixtures` | league fixture | 10,044 | the league model's feature matrix (home/away view) and market odds for benchmarking |
| `barca_matches` | Barcelona fixture | 996 | the same features from Barcelona's point of view |
| `xt_grid` | pitch cell | 192 | the 16 × 12 expected-threat surface |
| `player_ratings` | player × season | 5,971 | per-90 metrics, BIPR pillars and overall rating |
| `bipr_reference`, `match_rating_reference` | player-season / player-match | 320 / 7,758 | the fixed 2015/16 reference populations for ratings |
| `player_fixture` | player × Barcelona fixture | 11,417 | candidate table for the lineup model: recent minutes and starts, workload, form rating, previous-season rating, opponent strength, and whether the player started |

## Metric definitions

All defined once in `barca.analytics.definitions`
([D-012](decision-log.md#d-012---one-definitions-module-for-every-football-metric)).

| Metric | Definition |
|---|---|
| Completed pass | a pass with no outcome recorded |
| Progressive pass / carry | completed open-play pass, or any carry, starting at x ≥ 48 that gains ≥ 10 yards towards goal or enters the box from outside it |
| Final-third entry | completed pass or carry from x < 80 to x ≥ 80 |
| Box entry | completed pass or carry ending in the opponent's box from outside it (box: x ≥ 102, 18 ≤ y ≤ 62) |
| Key pass | pass that led directly to a shot |
| Long pass | pass of 35 yards or more |
| Big chance | non-penalty shot with xG ≥ 0.3 |
| Open-play / set-piece shot | open-play shot not from a corner, free kick or throw-in phase / every other non-penalty shot |
| Tackle won | duel of subtype Tackle with outcome Won, Success, Success In Play or Success Out |
| High recovery | successful recovery or won interception at x ≥ 80 |
| Turnover | miscontrol, dispossession or failed dribble |
| Touch | any on-ball event (pass, carry, dribble, shot, clearance, interception, recovery, miscontrol, dispossession, block, goalkeeper action, shield, 50/50) or a successful ball receipt |
| PPDA | opponent passes in their own 60% of the pitch ÷ (tackles + interceptions + fouls) in the pressing team's attacking 60%. Lower = more intense pressing |
| Possession | share of the match's passes (the usual public proxy) |
| Field tilt | share of the match's final-third passes |
| Defensive action height | mean x of pressures, tackles, interceptions, recoveries, clearances, blocks and fouls |
| Possession-adjusted defending | count × 0.5 ÷ opponent possession, clipped, so players of a possession-heavy team are not penalised for having less defending to do ([D-013](decision-log.md#d-013---minimum-minutes-and-possession-adjusted-defending)) |
| xT added | expected threat at the end location minus at the start, for completed passes and carries ([D-021](decision-log.md#d-021---expected-threat-fitted-on-the-complete-201516-season)) |

### Heatmap action families

| Family | Events |
|---|---|
| All actions | every on-ball event, ball receipts, pressures, duels, fouls committed and won |
| Touches | as defined above |
| Passing | passes |
| Carries | carries |
| Attacking | shots, key passes, dribbles, box entries, touches in the box |
| Defending | pressures, tackles, interceptions, recoveries, clearances, blocks, fouls, duels |

Heatmaps show where a player did recorded things with or around the ball,
not where the player was
([D-015](decision-log.md#d-015---heatmaps-are-action-heatmaps-and-the-app-says-so)).
