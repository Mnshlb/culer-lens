# Data quality

Event data breaks the usual cleaning playbook. `events.drop_nulls()` returns
zero rows, because every event type fills a different subset of the 72
columns, and dropping rows on `outcome` would keep only *failed* passes
(StatsBomb leaves the outcome of a completed pass empty). Quality therefore
rests on three pieces: profiling to learn what normal looks like, cleaning
rules tied to specific findings, and validation rules that know which fields
each event type must have.

## Profiling (notebook 07)

`barca.data.profile` describes every column of every processed table: type,
missing rate, distinct values, quantiles, IQR outliers, top values. The
output is `reports/data_profile.md`. Main conclusions:

- **Keys are clean**: no duplicate matches, events, fixtures or player-match
  rows.
- **Missingness is structural.** Per event type, the expected fields are
  complete.
- **Outliers are football, not errors.** Long passes, high-xG chances and
  long carries are real events and are kept. Only physically impossible
  values count as errors.
- **Coverage gaps are boundaries, not holes**: football-data shot and card
  statistics start in 2005/06, Pinnacle closing odds in 2012/13.

## Cleaning (`barca.data.clean`)

Eight rules, each traced to a finding. Nothing is imputed.

| Rule | Finding | Fix |
|---|---|---|
| C1 | 1,536 events with a start (325) or end (1,238) location up to 0.9 yards beyond the lines | clip to the 120 × 80 pitch |
| C2 | boolean flags (`under_pressure`, `pass_cross`, ...) are null when false | fill with false |
| C3 | an empty pass outcome means "complete" | explicit `pass_complete` column |
| C4 | lineup spells label three team-matches' starters as "Tactical Shift" | `started` comes from the Starting XI event |
| C5 | football-data spells Villarreal "Villareal" in early seasons | canonical club names from the crosswalk |
| C6 | football-data dates switch from `dd/mm/yy` to `dd/mm/yyyy` | length-aware date parsing |
| C7 | partition values say `2015-2016`, match metadata `2015/2016` | one canonical `season` column |
| C8 | penalty shoot-outs are not playing time | period 5 events dropped |

Before cleaning, two error rules fail (E07 locations, L02 starters). After
cleaning, every error rule passes
([D-017](decision-log.md#d-017---cleaning-is-minimal-and-traceable)).

## Validation (`barca.data.validate`)

38 rules, each with a table, a severity and a tolerance. The full current
result, with sample violating rows, is regenerated on every build in
`reports/data_quality.md`.

| Group | Rules | Examples |
|---|---|---|
| Events (E01-E22) | 22 | unique ids; index runs 1..n per match; valid clock per period; every shot has xG in (0, 1), an outcome and locations; every pass and carry has an end location; substitutions name a replacement from the same squad; every event player is in the matchday lineup; related-event and key-pass ids resolve inside the match; one Starting XI of 11 per team; **goals rebuilt from events equal the official score** |
| Matches (M01-M05) | 5 | unique ids; scores non-negative; date inside the season; **every league match agrees with football-data on date, teams and score** |
| Lineups (L01-L04) | 4 | minutes within the match length; exactly 11 starters; one team per player per match; team minutes consistent with 9-11 players on the pitch |
| Results (R01-R07) | 7 | one fixture per season, home and away; every season a complete double round robin; half-time goals ≤ full-time; shots ≥ shots on target; odds > 1; a club plays at most once per date |

The two cross-source rules (E22 and M05) give end-to-end confidence: all 869
official scores are reproduced from the event stream, and StatsBomb agrees
with football-data on all 866 league matches.

### Tolerated quirks

Three warning rules have a non-zero tolerance, each for a documented source
quirk rather than a defect:

| Rule | Count | Why it is tolerated |
|---|---|---|
| E05 | 1 | one ball receipt recorded with the previous period's number |
| E06 | 314 | related events recorded slightly out of timestamp order |
| L04 | 12 team-matches (0.7%) | a temporary injury exit overlaps a substitution in the lineup spells, so summed team minutes slightly exceed 11 players |

### The gate

`barca build` runs every rule and records the outcome in
`data/processed/_validation.json`. If any error-level rule fails, the build
exits with a non-zero code, and `barca features` refuses to run until a
build has passed
([D-016](decision-log.md#d-016---type-aware-validation-with-a-hard-gate-before-features)).
CI runs the same build and gate on a downloaded sample every week, because
upstream files can change without notice.

## Tests

- `tests/unit/test_validate.py` plants defects in small synthetic tables
  (duplicate ids, off-pitch locations, a shot without xG, a dangling
  key-pass reference) and checks that the right rule catches each one, that
  clean data passes, and that only error-level rules can fail the gate.
- `tests/data_quality/` runs every rule against the built data, plus the
  future-scrambling leakage test described in
  [feature-engineering.md](feature-engineering.md#proving-there-is-no-leakage).
