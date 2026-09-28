import type { Metadata } from "next";
import Image from "next/image";
import { PageTitle, Panel } from "@/components/common/ui";

export const metadata: Metadata = { title: "Methodology and limitations" };

const LIMITS: [string, string][] = [
  ["Event data is not tracking data",
   "StatsBomb records what happens on or around the ball: passes, carries, shots, pressures, tackles. It does not record where players are when they are not involved, how far they run or how fast."],
  ["Heatmaps show recorded actions",
   "Every heatmap is an action heatmap: where a player did something the data records. A player holding position or making a decoy run leaves no trace. Genuine coverage maps need tracking data."],
  ["The workload index is not medical fatigue",
   "It summarises league minutes, consecutive starts and rest with fixed reference points. It knows nothing about training load, sleep, travel or injuries, and cup and European matches are missing from the data, so real load is higher than shown."],
  ["Predictions are probabilities",
   "A 70% favourite is expected to fail to win three matches in ten. A single result can never prove a probability right or wrong; calibration over hundreds of matches can, and it is reported on the Model Intelligence page."],
  ["Ratings depend on the methodology",
   "BIPR is a transparent composite with published weights and a fixed reference population (La Liga 2015/16). Different, equally defensible choices would rank players differently. Players whose value is off the ball (positioning, press resistance) are under-rated by any event-based rating, and goalkeepers are not rated at all."],
  ["Dataset coverage is limited",
   "StatsBomb's open data covers Barcelona's league matches from 2004/05 to 2020/21 (incomplete before 2008/09, where it is centred on matches Lionel Messi played), the full 2015/16 league and three Champions League finals. Opponents otherwise appear only against Barcelona."],
  ["History does not guarantee the future",
   "Models learn patterns from past seasons. A new coach or a transformed squad breaks those patterns until results catch up: the model under-rated Guardiola's first two seasons by 11 and 18 points."],
  ["Team news is not in the model",
   "Injuries, suspensions and rotation plans are only partly visible (through the published matchday squad from 2015/16 onwards). This is the main reason the betting market, which prices team news, stays more accurate."],
  ["Public data is not club data",
   "Professional clubs combine event data with tracking, physical, medical and scouting data. This project shows what can be done rigorously with public data, not what a club analytics department has."],
];

export default function Page() {
  return (
    <div className="space-y-4">
      <PageTitle eyebrow="Methodology" title="How it works, and what it cannot do" />
      <Panel title="About this project">
        <div className="space-y-2 text-sm leading-relaxed text-muted-foreground">
          <p>
            Culer Lens is a <b className="text-foreground">personal, non-commercial project</b>. It is built on
            StatsBomb&apos;s free open data and football-data.co.uk&apos;s public results.
          </p>
          <p>
            It is <b className="text-foreground">not affiliated with, endorsed by or connected to FC Barcelona or
            StatsBomb</b>, or any other data source. Club and competition names are used only to identify teams and
            matches, and belong to their owners. The StatsBomb logo appears because StatsBomb asks for it as a data
            credit.
          </p>
        </div>
      </Panel>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Data">
          <div className="space-y-3 text-sm leading-relaxed text-muted-foreground">
            <p><b className="text-foreground">StatsBomb Open Data</b>: 3.1 million events from 869 matches (every Barcelona league match in the data, the complete 2015/16 La Liga season and three Champions League finals), with lineups, xG on every shot and 360 freeze frames for 2020/21.</p>
            <p><b className="text-foreground">football-data.co.uk</b>: every La Liga result since 1995/96 with shots, corners, cards and bookmaker odds. It powers the Elo ratings, every club&apos;s form, and the betting-market benchmark (odds are never model inputs).</p>
            <p>The raw data is not redistributed. The pipeline downloads it from the original sources at a pinned version and validates it with 38 football-aware data-quality rules before any feature is built.</p>
            <div className="flex items-center gap-2 text-xs">
              <span>Data by</span>
              <div className="inline-flex rounded-md bg-white px-2.5 py-1.5"><Image src="/statsbomb-logo.png" alt="StatsBomb" width={120} height={30} className="h-5 w-auto" /></div>
            </div>
          </div>
        </Panel>
        <Panel title="The time machine">
          <div className="space-y-3 text-sm leading-relaxed text-muted-foreground">
            <p>The data ends in May 2021, so the platform does not pretend to predict next weekend. Instead, every fixture from 2008/09 onwards can be viewed <b className="text-foreground">as it would have looked that morning</b>: the prediction, the predicted XI, form and workload are all computed only from earlier matches, by models trained only on earlier seasons.</p>
            <p>A future-scrambling test enforces this: results after a cut-off date are randomised, the features are rebuilt, and nothing on or before the cut-off may change.</p>
          </div>
        </Panel>
        <Panel title="Match prediction">
          <div className="space-y-3 text-sm leading-relaxed text-muted-foreground">
            <p>An equal-weight ensemble of three models trained on every La Liga fixture since 2005/06: an ordered logit on the Elo gap, a Poisson goals model (which also gives expected goals and scorelines) and LightGBM on 90 form, strength and context features.</p>
            <p>Chosen on 2008/09-2013/14 and evaluated on the untouched 2014/15-2020/21 seasons, walk-forward. It beats every single model and closes most of the gap between base rates and the betting market. Explanations are SHAP values of the exact model that made each prediction.</p>
          </div>
        </Panel>
        <Panel title="Players">
          <div className="space-y-3 text-sm leading-relaxed text-muted-foreground">
            <p><b className="text-foreground">BIPR</b> rates players on seven pillars (passing, creation, progression, carrying, defending, shooting, ball security) as percentiles within their position family, with possession-adjusted defending and expected threat for ball progression. <b className="text-foreground">Match ratings</b> map the same pillars onto a 3-10 scale centred on 6.5.</p>
            <p>The <b className="text-foreground">starting XI</b> combines calibrated start probabilities with the expected formation and a position-constrained assignment: about 9 of 11 starters right on the holdout seasons.</p>
          </div>
        </Panel>
      </div>
      <Panel title="Limitations">
        <dl className="grid gap-x-10 gap-y-5 md:grid-cols-2">
          {LIMITS.map(([t, d]) => (
            <div key={t}>
              <dt className="text-sm font-medium">{t}</dt>
              <dd className="mt-1 text-sm leading-relaxed text-muted-foreground">{d}</dd>
            </div>
          ))}
        </dl>
      </Panel>
    </div>
  );
}
