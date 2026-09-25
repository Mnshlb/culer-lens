"use client";

import { Calibration, TrendChart } from "@/components/charts/line-charts";
import { Bars } from "@/components/charts/contributions";
import { ConfusionMatrix } from "@/components/charts/matrix";
import { ErrorState, InfoTip, Loading, PageTitle, Panel, ResultChip, Stat } from "@/components/common/ui";
import { useModel, useModelExplanation, useModels } from "@/lib/api";
import { date as fmtDate, num, pct } from "@/lib/format";
import { colors } from "@/lib/theme";
import Link from "next/link";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Metric = { log_loss: number; brier: number; rps: number; accuracy: number; ece: number; n: number };

export function ModelIntelligence() {
  const models = useModels();
  const outcome = useModel(1);
  const exp = useModelExplanation(1);
  if (outcome.error) return <ErrorState error={outcome.error} />;
  if (!outcome.data || !exp.data) return <Loading className="h-[80vh]" />;
  const ev = outcome.data.evaluation;
  const card = outcome.data.card;
  const hold: Partial<Metric> = card?.metrics?.league_holdout ?? ev?.metrics?.league_holdout ?? {};
  const lineup = models.data?.find((m) => m.kind === "lineup");
  const calib = ev.calibration ?? {};

  return (
    <div className="space-y-4">
      <PageTitle eyebrow="Model Intelligence" title="How the predictions are made, and how good they are" />

      <div className="grid gap-4 lg:grid-cols-[1.1fr_1fr]">
        <Panel title="Match outcome model" subtitle={`${outcome.data.name} · ${outcome.data.description}`}>
          <div className="grid grid-cols-2 gap-5 md:grid-cols-4">
            <Stat label="Log loss" value={num(hold.log_loss, 3)} sub="holdout, lower is better" />
            <Stat label="Brier score" value={num(hold.brier, 3)} sub="multi-class" />
            <Stat label="RPS" value={num(hold.rps, 3)} sub="ranked probability" />
            <Stat label="Calibration error" value={num(hold.ece, 3)} sub="ECE" />
          </div>
          <div className="mt-5 rounded-lg bg-surface-2 p-4 text-sm leading-relaxed text-muted-foreground">
            Walk-forward: every season from 2008/09 is predicted by a model trained only on earlier La Liga seasons (all clubs,
            from 2005/06). Design choices were made on 2008/09-2013/14; the {hold.n?.toLocaleString() ?? "holdout"} matches of 2014/15-2020/21
            are the untouched holdout reported here. Accuracy ({pct(hold.accuracy)}) is shown but not optimised: it ignores
            everything a probability says except which outcome is biggest.
          </div>
        </Panel>
        <Panel title="Against the benchmarks" subtitle="Holdout seasons 2014/15-2020/21, all La Liga fixtures">
          <table className="w-full text-sm">
            <thead className="text-xs text-muted-foreground">
              <tr><th className="pb-2 text-left font-medium">Model</th><th className="pb-2 text-right font-medium">Log loss</th><th className="pb-2 text-right font-medium">RPS</th><th className="pb-2 text-right font-medium">Accuracy</th></tr>
            </thead>
            <tbody>
              {(ev.holdout_models as (Metric & { model: string })[]).map((r) => (
                <tr key={r.model} className="border-t border-border">
                  <td className={`py-2 ${r.model.startsWith("Production") ? "font-semibold text-foreground" : "text-muted-foreground"}`}>{r.model}</td>
                  <td className="py-2 text-right tabular">{num(r.log_loss, 4)}</td>
                  <td className="py-2 text-right tabular">{num(r.rps, 4)}</td>
                  <td className="py-2 text-right tabular">{pct(r.accuracy, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
            The betting market prices team news, injuries and informed money that no results-based model sees, so it is the
            ceiling. The ensemble closes most of the gap between base rates and the market.
          </p>
        </Panel>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {(["home_win", "draw", "away_win"] as const).map((k) => (
          <Panel key={k} title={`Calibration · ${k.replace("_", " ")}`} subtitle="x: predicted probability · y: observed frequency">
            <Calibration series={[
              { name: "Ensemble", color: colors.barca, points: calib[k]?.model ?? [] },
              { name: "Market", color: colors.opponent, points: calib[k]?.market ?? [] },
            ]} height={230} />
          </Panel>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="What drives predictions" subtitle="Grouped permutation importance, holdout"
               action={<InfoTip>Increase in log loss when a group of related features is shuffled, measured out of sample season by season. Groups avoid under-counting near-duplicate features.</InfoTip>}>
          <Bars items={(exp.data.permutation as { group: string; increase: number }[]).map((p) => ({ label: p.group, value: Math.max(0, p.increase) }))} />
          <p className="mt-3 text-xs text-muted-foreground">Elo already summarises form, so once it is known the separate form features add little.</p>
        </Panel>
        <Panel title="SHAP summary" subtitle="LightGBM member, mean |SHAP| (top 12)">
          <Bars color={colors.opponent} items={(exp.data.tree_shap as { label: string; mean_abs_shap: number }[]).slice(0, 12).map((r) => ({ label: r.label, value: r.mean_abs_shap }))} />
          <p className="mt-3 text-xs text-muted-foreground">
            Audit: none of the top features is a post-match quantity{exp.data.audit_flags?.length ? ` (flags: ${exp.data.audit_flags.join(", ")})` : ""}.
          </p>
        </Panel>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <Panel title="Season backtest" subtitle="Log loss per season (lower is better)">
          <TrendChart
            data={(ev.seasons as { season: string; ensemble: number; elo: number; market: number }[]).map((s) => ({ ...s, label: s.season.slice(2, 4) + "/" + s.season.slice(7, 9) }))}
            xKey="label"
            series={[{ key: "ensemble", name: "Ensemble", color: colors.barca }, { key: "elo", name: "Elo baseline", color: colors.draw }, { key: "market", name: "Market", color: colors.opponent }]}
            height={260}
          />
          <p className="mt-2 text-xs text-muted-foreground">2008/09-2013/14 development seasons · 2014/15-2020/21 holdout. Season difficulty moves all three lines together.</p>
        </Panel>
        <Panel title="Confusion matrix" subtitle="Holdout, most likely outcome vs actual">
          <ConfusionMatrix matrix={ev.confusion} labels={["Home", "Draw", "Away"]} />
          <p className="mt-3 text-xs text-muted-foreground">
            A draw is rarely the single most likely outcome, even when it is quite likely, so almost no draws are picked.
            That is expected behaviour for a calibrated model, and why accuracy is not the target.
          </p>
        </Panel>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
        <Panel title="Opponent strength (PDP / ICE)" subtitle={`P(Barcelona win) at home vs opponent Elo, ${exp.data.pdp.season}`}>
          <Pdp pdp={exp.data.pdp} />
        </Panel>
        <Panel title="High-confidence misses" subtitle="Barcelona fixtures where the model gave ≥ 70% to an outcome that did not happen"
               bodyClassName="p-0">
          <div className="max-h-[340px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-card text-xs text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="px-5 py-2 text-left font-medium">Match</th>
                  <th className="px-2 py-2 text-right font-medium">P(win)</th>
                  <th className="px-2 py-2 text-right font-medium">xG</th>
                  <th className="px-5 py-2 text-right font-medium">Note</th>
                </tr>
              </thead>
              <tbody>
                {(ev.errors as Record<string, string | number | boolean | null>[]).slice(0, 30).map((e) => (
                  <tr key={String(e.fixture_id)} className="border-b border-border/60">
                    <td className="px-5 py-2">
                      <span className="flex items-center gap-2">
                        <ResultChip result={String(e.barca_result)} size="sm" />
                        <span className="text-xs text-muted-foreground tabular">{fmtDate(String(e.date), { day: "2-digit", month: "short", year: "2-digit" })}</span>
                        <span className="truncate">{e.is_home ? "vs" : "at"} {String(e.opponent)} <span className="text-muted-foreground tabular">{String(e.barca_goals)}-{String(e.opp_goals)}</span></span>
                      </span>
                    </td>
                    <td className="px-2 py-2 text-right tabular">{pct(Number(e.p_win))}</td>
                    <td className="px-2 py-2 text-right tabular text-muted-foreground">{e.barca_xg == null ? "–" : `${num(Number(e.barca_xg), 1)}–${num(Number(e.opp_xg), 1)}`}</td>
                    <td className="px-5 py-2 text-right text-xs text-muted-foreground">
                      {Number(e.barca_reds) > 0 ? "Barça red card" : e.barca_xg != null && Number(e.barca_xg) > Number(e.opp_xg) ? "out-created opponent" : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="px-5 py-2 text-[11px] text-muted-foreground">
            Among fixtures called at ≥ 70%, the model expects roughly as many misses as occurred: these are the one-in-four
            upsets a 75% favourite should suffer.
          </p>
        </Panel>
      </div>

      {lineup && (
        <Panel title="Starting XI model" subtitle={`${lineup.name} · ${lineup.description}`}>
          <div className="grid grid-cols-2 gap-5 md:grid-cols-4">
            <Stat label="Starters correct, holdout" value={num(Number(lineup.headline.holdout_mean_correct), 2)} sub="of 11, 2014/15-2020/21" />
            <Stat label="Starters correct, development" value={num(Number(lineup.headline.dev_mean_correct), 2)} sub="of 11, 2008/09-2013/14" />
            <Stat label="Fixtures evaluated" value={String(lineup.headline.evaluated)} />
            <Stat label="Baseline: same XI as last match" value="7.78" sub="holdout, of 11" />
          </div>
          <p className="mt-4 text-sm text-muted-foreground">
            Start probabilities (LightGBM, walk-forward) → expected formation → position-constrained assignment. See the{" "}
            <Link href="/about" className="text-primary hover:underline">methodology</Link>.
          </p>
        </Panel>
      )}
    </div>
  );
}

function Pdp({ pdp }: { pdp: { grid: number[]; average: number[]; ice: number[][] } }) {
  const data = pdp.grid.map((g, i) => {
    const row: Record<string, number> = { elo: Math.round(g), avg: pdp.average[i] };
    pdp.ice.forEach((c, j) => { row[`i${j}`] = c[i]; });
    return row;
  });
  return (
    <div>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={colors.grid} vertical={false} />
          <XAxis dataKey="elo" type="number" domain={[1400, 1750]} ticks={[1400, 1450, 1500, 1550, 1600, 1650, 1700, 1750]}
                 stroke={colors.axis} tick={{ fill: colors.muted, fontSize: 11 }} tickLine={false} />
          <YAxis domain={[0, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} stroke={colors.axis}
                 tick={{ fill: colors.muted, fontSize: 11 }} tickLine={false} width={46} />
          <Tooltip contentStyle={{ background: "#1a1e28", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, fontSize: 12 }}
                   formatter={(v) => `${(Number(v) * 100).toFixed(1)}%`} labelFormatter={(l) => `Opponent Elo ${l}`}
                   filterNull itemSorter={() => 0} />
          {pdp.ice.map((_, j) => (
            <Line key={j} dataKey={`i${j}`} stroke="rgba(255,255,255,0.18)" strokeWidth={1} dot={false} isAnimationActive={false} legendType="none" name="match" />
          ))}
          <Line dataKey="avg" name="Average" stroke={colors.barca} strokeWidth={2.5} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
      <p className="mt-2 text-xs text-muted-foreground">Garnet: average effect. Grey: one curve per home match. Parallel curves mean the effect has the same shape in every match.</p>
    </div>
  );
}
