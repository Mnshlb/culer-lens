"use client";

import { ArrowRight, Eye, EyeOff } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useState } from "react";
import { Contributions } from "@/components/charts/contributions";
import { Meter, READINESS_BANDS, WORKLOAD_BANDS } from "@/components/charts/meter";
import { ProbabilityBar } from "@/components/charts/probability-bar";
import { ScoreList } from "@/components/charts/scores";
import { AsOfPicker } from "@/components/common/as-of-picker";
import { ErrorState, InfoTip, Loading, PageTitle, Panel, ResultChip, Stat } from "@/components/common/ui";
import { Button } from "@/components/ui/button";
import { useOverview } from "@/lib/api";
import { date as fmtDate, int, num, pct } from "@/lib/format";
import { bandColor } from "@/lib/theme";

export function Dashboard({ asOf, season }: { asOf?: string; season?: string }) {
  const { data, error, isLoading } = useOverview(asOf);
  const [revealed, setRevealed] = useState(false);
  if (error) return <ErrorState error={error} />;
  if (isLoading || !data) return <Loading className="h-[70vh]" />;

  const m = data.next_match;
  const p = data.prediction;
  const opp = m.opponent;
  const home = m.barca_home ? "Barcelona" : opp.name;
  const away = m.barca_home ? opp.name : "Barcelona";
  const readiness = data.readiness as { score: number; form_score: number; freshness: number; method: string } | null;
  const rec = data.season_record as Record<string, number>;

  return (
    <div>
      <PageTitle eyebrow={`As of ${fmtDate(data.as_of)}`} title="What's happening with Barcelona">
        <AsOfPicker season={season ?? m.season} matchId={m.id} />
      </PageTitle>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel
          className="lg:col-span-2"
          title="Next match"
          subtitle={`${m.competition} · ${fmtDate(m.date, { weekday: "long", day: "numeric", month: "long", year: "numeric" })}`}
          action={
            <Button variant="ghost" size="sm" onClick={() => setRevealed((r) => !r)} className="text-muted-foreground">
              {revealed ? <EyeOff className="mr-1.5 h-4 w-4" /> : <Eye className="mr-1.5 h-4 w-4" />}
              {revealed ? "Hide result" : "Reveal result"}
            </Button>
          }
        >
          <div className="grid gap-6 md:grid-cols-[1.2fr_1fr]">
            <div className="space-y-6">
              <div className="flex items-center justify-between gap-4">
                <TeamName name={home} code={m.barca_home ? "BAR" : opp.code} align="left" />
                <div className="text-center">
                  {revealed ? (
                    <motion.div initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="space-y-1">
                      <div className="text-3xl font-semibold tabular">
                        {m.barca_home ? `${m.barca_goals}-${m.opponent_goals}` : `${m.opponent_goals}-${m.barca_goals}`}
                      </div>
                      <ResultChip result={m.result} size="sm" />
                    </motion.div>
                  ) : (
                    <span className="text-sm text-muted-foreground">vs</span>
                  )}
                </div>
                <TeamName name={away} code={m.barca_home ? opp.code : "BAR"} align="right" />
              </div>

              {p ? (
                <>
                  <div className="flex items-end gap-3">
                    <motion.span
                      key={m.id}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="text-6xl font-semibold tracking-tight"
                    >
                      {pct(p.probabilities.win)}
                    </motion.span>
                    <span className="mb-2 text-sm text-muted-foreground">chance of a Barça win</span>
                  </div>
                  <ProbabilityBar p={p.probabilities} market={p.market} labels={["Barça", "Draw", opp.short_name]} />
                  <div className="grid grid-cols-2 gap-4 rounded-lg bg-surface-2 p-4">
                    <Stat label="Expected goals · Barça" value={num(p.expected_goals.barca, 2)} />
                    <Stat label={`Expected goals · ${opp.short_name}`} value={num(p.expected_goals.opponent, 2)} />
                  </div>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No prediction: neutral-venue finals are outside the league model.
                </p>
              )}
            </div>
            <div className="space-y-5">
              {p && (
                <div>
                  <p className="mb-2 text-xs font-medium text-muted-foreground">Most likely scores</p>
                  <ScoreList scores={p.top_scores} actual={revealed ? [m.barca_goals, m.opponent_goals] : undefined} />
                </div>
              )}
              {p?.explanation && (
                <div>
                  <p className="mb-2 text-xs font-medium text-muted-foreground">What drives the prediction</p>
                  <Contributions items={p.explanation.contributions} max={4} compact />
                </div>
              )}
              <Button asChild className="w-full">
                <Link href={`/matches/${m.id}`}>
                  Open match centre <ArrowRight className="ml-1.5 h-4 w-4" />
                </Link>
              </Button>
            </div>
          </div>
        </Panel>

        <div className="grid gap-4">
          <Panel title="Form" subtitle="Last five matches before this one">
            <div className="space-y-2">
              {data.form.length === 0 && <p className="text-sm text-muted-foreground">No earlier recorded fixtures.</p>}
              {data.form.map((f) => (
                <Link key={f.id} href={`/matches/${f.id}`} className="flex items-center gap-3 rounded-md px-1 py-1 text-sm hover:bg-secondary">
                  <ResultChip result={f.result} size="sm" />
                  <span className="w-14 text-xs text-muted-foreground">{fmtDate(f.date, { day: "numeric", month: "short" })}</span>
                  <span className="flex-1 truncate">{f.barca_home ? "vs" : "at"} {f.opponent.short_name}</span>
                  <span className="tabular font-medium">{f.barca_goals}-{f.opponent_goals}</span>
                </Link>
              ))}
            </div>
          </Panel>
          <Panel
            title="Team readiness"
            action={readiness && <InfoTip>{readiness.method}</InfoTip>}
          >
            {readiness ? (
              <div className="space-y-4">
                <div className="flex items-baseline gap-1.5">
                  <span className="text-4xl font-semibold tracking-tight">{readiness.score}</span>
                  <span className="text-sm text-muted-foreground">/ 100</span>
                </div>
                <Meter value={readiness.score} bands={READINESS_BANDS} />
                <div className="grid grid-cols-2 gap-3 text-xs text-muted-foreground">
                  <span>Form of predicted XI <b className="text-foreground">{readiness.form_score}</b></span>
                  <span>Freshness <b className="text-foreground">{readiness.freshness}</b></span>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No lineup prediction for this fixture.</p>
            )}
          </Panel>
        </div>

        <Panel title="Season so far" subtitle={m.season}>
          <div className="grid grid-cols-4 gap-4">
            <Stat label="Played" value={int(rec.played)} />
            <Stat label="Points" value={int(rec.points)} sub={rec.played ? `${num(rec.points / rec.played, 2)} per game` : undefined} />
            <Stat label="W-D-L" value={<span className="text-xl">{rec.won}-{rec.drawn}-{rec.lost}</span>} />
            <Stat label="Goals" value={<span className="text-xl">{rec.goals_for}:{rec.goals_against}</span>} />
          </div>
          <div className="mt-5 flex items-center justify-between rounded-lg bg-surface-2 px-4 py-3 text-sm">
            <span className="text-muted-foreground">Elo rating going in</span>
            <span className="font-semibold tabular">{int(data.elo)}</span>
          </div>
        </Panel>

        <Panel
          className="lg:col-span-2"
          title="Highest workload in the squad"
          subtitle="Observed league minutes before this fixture (not a fatigue measure)"
          action={<InfoTip>Workload index 0-100 from minutes in the last 7/14/30 days, consecutive starts and rest. Cup and European minutes are not in the data, so real load is higher.</InfoTip>}
        >
          <div className="grid gap-x-8 gap-y-4 md:grid-cols-2">
            {data.high_workload.map((pl) => (
              <Link key={pl.player_id} href={`/players/${pl.player_id}`} className="group block">
                <div className="mb-1.5 flex items-baseline justify-between text-sm">
                  <span className="font-medium group-hover:text-primary">{pl.name}</span>
                  <span className="text-xs text-muted-foreground">
                    <span className="mr-2 inline-block h-2 w-2 rounded-full" style={{ background: bandColor[pl.workload_band] }} />
                    {pl.workload_band} · <b className="text-foreground tabular">{Math.round(pl.workload_index)}</b>
                  </span>
                </div>
                <Meter value={pl.workload_index} bands={WORKLOAD_BANDS} height={6} />
              </Link>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function TeamName({ name, code, align }: { name: string; code: string; align: "left" | "right" }) {
  const barca = name === "Barcelona";
  return (
    <div className={align === "right" ? "text-right" : ""}>
      <p className="text-[11px] font-semibold tracking-[0.2em] text-muted-foreground">{code}</p>
      <p className={`text-xl font-semibold md:text-2xl ${barca ? "text-foreground" : "text-foreground/90"}`}>{name}</p>
    </div>
  );
}
