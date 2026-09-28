# Limitations

What this platform cannot do, and why. The same list, in shorter form, is on
the app's Methodology page.

## Data

**Event data is not tracking data.** StatsBomb records what happens on or
around the ball. It does not record where players are when they are not
involved, how far they run or how fast. Anything physical (distance,
sprints, off-ball movement) is out of reach.

**Heatmaps show recorded actions, not coverage.** A player holding position
or making a decoy run leaves no trace. Every heatmap is labelled as an
action heatmap.

**Coverage is partial and uneven.** Barcelona's league matches from 2004/05
to 2020/21, incomplete before 2008/09 and centred on matches Lionel Messi
played in the early seasons; the full 2015/16 league; three Champions League
finals. Outside 2015/16, opponents only appear against Barcelona, so their
event-based style is only known in this one fixture, where they play
differently (deeper, less possession).

**No cup or European matches** (apart from the three finals). Player minutes,
workload and form therefore describe league football only.

**The data ends in May 2021.** There is no real "next match" to predict. The
app replays history instead: every prediction is shown as it would have been
made before kick-off.

**Partial squad information.** The matchday squad (who was available) is
recorded from 2015/16. Before that, the candidate pool for the lineup model
is everyone who played in the previous 60 days, which includes players who
were injured or suspended.

**No goalkeeper metrics.** Shot-stopping needs post-shot xG, which the open
data does not include, so goalkeepers get no BIPR.

**No player ages or contracts.** The data has no dates of birth.

## Models

**Team news is not in the model.** Injuries, suspensions and rotation plans
are the main reason the betting market stays more accurate (0.953 vs 0.968
log loss on the holdout seasons). Where the model and market disagree most,
the market is usually right, so the model is not a betting signal.

**Results-based strength lags real change.** A new coach or a rebuilt squad
takes months to show up in Elo and form. The model under-rated Guardiola's
first two seasons by 11 and 18 points.

**Predictions are probabilities.** A 70% favourite should fail to win three
matches in ten. A single result proves nothing about a probability;
calibration over hundreds of matches does, and it is reported on the Model
Intelligence page.

**Draws are rarely the most likely outcome**, so the model almost never
"picks" one even though about a quarter of matches are drawn. That is a
property of honest three-way probabilities, not a defect, and it is why
accuracy is not the headline metric.

**Small sample for model selection.** 2,280 development fixtures are enough
to rank model families but not to tune dozens of hyperparameters; tuning
overfitted and was dropped.
Single-model rankings shuffled between development and holdout seasons,
which is why production averages three models.

**Starting XI.** About 9 of 11 starters are predicted correctly on the
holdout seasons, but the whole XI only in about 12% of matches. The model
sees selection history, not training, fitness or tactics.

## Ratings and indices

**Ratings depend on methodology.** BIPR's pillars, weights and reference
population are published, but other defensible choices would rank players
differently. Off-ball value (positioning, press resistance) is under-rated by
any event-based rating; Busquets is the clearest example.

**Per-90 rates are noisy below 900 minutes.** Such players are shown with a
low-sample flag instead of a rating.

**The Workload Index is not fatigue.** It summarises observed league minutes,
starts and rest with fixed reference points. It knows nothing about training
load, travel, sleep or injuries, and it understates real load because cup and
European matches are missing
([workload-methodology.md](workload-methodology.md)).

**Team readiness is a summary, not a model.** It combines the predicted
XI's form and freshness with fixed weights, and has not been validated as a
predictor of results.

**Explanations describe the model, not the game.** SHAP contributions say
why the model produced a number, not what caused the result. Correlated
features share credit, so the grouped view is the more reliable reading.

## Scope

**Public data is not club data.** Professional clubs combine event data with
tracking, physical, medical and scouting information. This project shows
what can be done rigorously with public data, not what a club analytics
department has.
