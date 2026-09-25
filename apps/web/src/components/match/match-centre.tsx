"use client";

import { ChevronLeft, ChevronRight, Eye, EyeOff } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { Contributions } from "@/components/charts/contributions";
import { Meter, WORKLOAD_BANDS } from "@/components/charts/meter";
import { ProbabilityBar } from "@/components/charts/probability-bar";
import { ScoreList } from "@/components/charts/scores";
import { Empty, ErrorState, InfoTip, Loading, Panel, ResultChip } from "@/components/common/ui";
import { LineupPitch } from "@/components/pitch/lineup-pitch";
import { PassNetwork } from "@/components/pitch/pass-network";
import { ShotMap } from "@/components/pitch/shot-map";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { type LineupPlayer, type MatchDetail, useMatch, useMatches, usePasses, useShots } from "@/lib/api";
import { date as fmtDate, int, num, pct } from "@/lib/format";
import { bandColor, colors } from "@/lib/theme";
import { PlayerSheet } from "./player-sheet";

export function MatchCentre({ id }: { id: number }) {
  const { data, error, isLoading } = useMatch(id);
  const [revealed, setRevealed] = useState(false);
  const [selected, setSelected] = useState<LineupPlayer | null>(null);
  if (error) return <ErrorState error={error} />;
  if (isLoading || !data) return <Loading className="h-[80vh]" />;
  const m = data.match;
  return (
    <div className="space-y-4">
      <Header data={data} revealed={revealed} onToggle={() => setRevealed((r) => !r)} />
      <div className="grid gap-4 lg:grid-cols-[1.25fr_1fr]">
        <PredictionPanel data={data} revealed={revealed} />
        <Comparison data={data} />
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <Panel
          title="Predicted XI"
          subtitle={data.lineup ? `${formation(data.lineup.formation)} · ring = start probability · click a player` : undefined}
          action={revealed && data.lineup?.correct != null ? (
            <span className="rounded-md bg-surface-2 px-2.5 py-1 text-xs"><b className="text-foreground">{data.lineup.correct}/11</b> <span className="text-muted-foreground">started</span></span>
          ) : undefined}
        >
          {data.lineup ? (
            <div className="grid gap-4 md:grid-cols-[1fr_180px]">
              <div className="mx-auto w-full max-w-[420px]">
                <LineupPitch players={data.lineup.predicted_xi} selected={selected?.player_id} onSelect={setSelected} revealed={revealed} />
              </div>
              <div>
                <p className="mb-2 text-xs font-medium text-muted-foreground">Next most likely</p>
                <ul className="space-y-1">
                  {data.lineup.others.slice(0, 9).map((p) => (
                    <li key={p.player_id}>
                      <button onClick={() => setSelected(p)} className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm hover:bg-secondary">
                        <span className="truncate">{p.name}</span>
                        <span className="ml-2 text-xs tabular text-muted-foreground">{pct(p.p_start)}</span>
                      </button>
                    </li>
                  ))}
                </ul>
                {revealed && data.lineup.actual_xi.length > 0 && (
                  <p className="mt-3 text-xs text-muted-foreground">Red outline = predicted but did not start.</p>
                )}
              </div>
            </div>
          ) : (
            <Empty>No lineup prediction for this fixture.</Empty>
          )}
        </Panel>
        <Panel title="Why this prediction?" subtitle="SHAP contributions of the model that made it"
               action={<InfoTip>Permutation SHAP of the production ensemble, trained only on seasons before this match. Contributions add up exactly to the predicted probability.</InfoTip>}>
          {data.prediction?.explanation ? (
            <div className="space-y-5">
              <Contributions items={data.prediction.explanation.contributions} max={9} />
              <GroupTotals groups={data.prediction.explanation.groups} base={data.prediction.explanation.base_value} p={data.prediction.probabilities.win} />
            </div>
          ) : (
            <Empty>No explanation for this fixture.</Empty>
          )}
        </Panel>
      </div>
      {data.lineup && (
        <Panel title="Workload of the predicted XI" subtitle="Observed league minutes before kick-off">
          <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
            {[...data.lineup.predicted_xi].sort((a, b) => b.workload_index - a.workload_index).map((p) => (
              <button key={p.player_id} onClick={() => setSelected(p)} className="block text-left">
                <div className="mb-1 flex items-baseline justify-between text-sm">
                  <span className="font-medium hover:text-primary">{p.name}</span>
                  <span className="text-xs text-muted-foreground">
                    <span className="mr-1.5 inline-block h-2 w-2 rounded-full" style={{ background: bandColor[p.workload_band] }} />
                    {p.workload_band} <b className="ml-1 text-foreground">{Math.round(p.workload_index)}</b>
                  </span>
                </div>
                <Meter value={p.workload_index} bands={WORKLOAD_BANDS} height={5} />
              </button>
            ))}
          </div>
        </Panel>
      )}
      {m.has_events && (revealed ? <MatchAnalysis data={data} /> : (
        <Panel title="Match analysis">
          <div className="flex flex-col items-center gap-3 py-6 text-center text-sm text-muted-foreground">
            <p>Shot map, pass network and match statistics are hidden until the result is revealed.</p>
            <Button variant="secondary" onClick={() => setRevealed(true)}><Eye className="mr-1.5 h-4 w-4" />Reveal result</Button>
          </div>
        </Panel>
      ))}
      <PlayerSheet player={selected} date={m.date} onClose={() => setSelected(null)} />
    </div>
  );
}

const formation = (f: string | null | undefined) => (f ? f.split("").join("-") : "Formation unknown");

function Header({ data, revealed, onToggle }: { data: MatchDetail; revealed: boolean; onToggle: () => void }) {
  const m = data.match;
  const list = useMatches(m.season);
  const idx = list.data?.findIndex((x) => x.id === m.id) ?? -1;
  const prev = idx > 0 ? list.data?.[idx - 1] : undefined;
  const next = idx >= 0 ? list.data?.[idx + 1] : undefined;
  const home = m.barca_home ? { name: "Barcelona", code: "BAR" } : { name: m.opponent.name, code: m.opponent.code };
  const away = m.barca_home ? { name: m.opponent.name, code: m.opponent.code } : { name: "Barcelona", code: "BAR" };
  const [hg, ag] = m.barca_home ? [m.barca_goals, m.opponent_goals] : [m.opponent_goals, m.barca_goals];
  return (
    <div className="rounded-2xl border border-border bg-card px-5 py-5 md:px-8">
      <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
        <span>
          {m.competition} · {m.season} · {fmtDate(m.date, { weekday: "short", day: "numeric", month: "long", year: "numeric" })}
          {m.era ? ` · ${m.era}` : ""}
        </span>
        <div className="flex items-center gap-1">
          <Button asChild variant="ghost" size="icon" disabled={!prev} className="h-8 w-8">
            <Link href={prev ? `/matches/${prev.id}` : "#"} aria-label="Previous fixture"><ChevronLeft className="h-4 w-4" /></Link>
          </Button>
          <Button asChild variant="ghost" size="icon" disabled={!next} className="h-8 w-8">
            <Link href={next ? `/matches/${next.id}` : "#"} aria-label="Next fixture"><ChevronRight className="h-4 w-4" /></Link>
          </Button>
        </div>
      </div>
      <div className="mt-4 grid grid-cols-[1fr_auto_1fr] items-center gap-4">
        <div>
          <p className="text-xs font-semibold tracking-[0.2em] text-muted-foreground">{home.code}</p>
          <p className="text-2xl font-semibold md:text-4xl">{home.name}</p>
        </div>
        <div className="text-center">
          {revealed ? (
            <div className="space-y-1.5">
              <p className="text-4xl font-semibold tabular md:text-5xl">{hg}<span className="mx-2 text-muted-foreground">–</span>{ag}</p>
              <ResultChip result={m.result} size="sm" />
            </div>
          ) : (
            <p className="text-lg text-muted-foreground">vs</p>
          )}
          <Button variant="ghost" size="sm" onClick={onToggle} className="mt-1 text-xs text-muted-foreground">
            {revealed ? <EyeOff className="mr-1 h-3.5 w-3.5" /> : <Eye className="mr-1 h-3.5 w-3.5" />}
            {revealed ? "Hide result" : "Reveal result"}
          </Button>
        </div>
        <div className="text-right">
          <p className="text-xs font-semibold tracking-[0.2em] text-muted-foreground">{away.code}</p>
          <p className="text-2xl font-semibold md:text-4xl">{away.name}</p>
        </div>
      </div>
    </div>
  );
}

function PredictionPanel({ data, revealed }: { data: MatchDetail; revealed: boolean }) {
  const p = data.prediction;
  const m = data.match;
  if (!p) return <Panel title="Prediction"><Empty>Neutral-venue finals are outside the league model.</Empty></Panel>;
  return (
    <Panel title="Prediction" subtitle={`Made before kick-off by ${p.model}`}>
      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-5">
          <div className="grid grid-cols-3 gap-2">
            {(["win", "draw", "loss"] as const).map((k) => (
              <div key={k} className="rounded-lg bg-surface-2 p-3">
                <p className="text-[11px] text-muted-foreground">{k === "win" ? "Barça win" : k === "draw" ? "Draw" : `${m.opponent.short_name} win`}</p>
                <p className="mt-1 text-2xl font-semibold tabular">{pct(p.probabilities[k])}</p>
              </div>
            ))}
          </div>
          <ProbabilityBar p={p.probabilities} market={p.market} labels={["Barça", "Draw", m.opponent.short_name]} />
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-lg border border-border p-3"><p className="text-[11px] text-muted-foreground">Expected goals · Barça</p><p className="text-xl font-semibold">{num(p.expected_goals.barca, 2)}</p></div>
            <div className="rounded-lg border border-border p-3"><p className="text-[11px] text-muted-foreground">Expected goals · {m.opponent.short_name}</p><p className="text-xl font-semibold">{num(p.expected_goals.opponent, 2)}</p></div>
          </div>
        </div>
        <div>
          <p className="mb-2 text-xs font-medium text-muted-foreground">Likely scores</p>
          <ScoreList scores={p.top_scores} actual={revealed ? [m.barca_goals, m.opponent_goals] : undefined} />
          <p className="mt-3 text-[11px] text-muted-foreground">From the Poisson goals model: the chance of each exact scoreline. Probabilities, not picks.</p>
        </div>
      </div>
    </Panel>
  );
}

function Comparison({ data }: { data: MatchDetail }) {
  const b = data.comparison.barca;
  const o = data.comparison.opponent;
  const rows: { label: string; b: string; o: string; better?: "b" | "o" | null }[] = [
    { label: "Elo rating", b: int(b.elo), o: int(o.elo), better: cmp(b.elo, o.elo) },
    { label: "Points per game, last 5", b: num(b.points_5, 1), o: num(o.points_5, 1), better: cmp(b.points_5, o.points_5) },
    { label: "Goals scored, last 10", b: num(b.goals_10, 1), o: num(o.goals_10, 1), better: cmp(b.goals_10, o.goals_10) },
    { label: "Goals conceded, last 10", b: num(b.goals_against_10, 1), o: num(o.goals_against_10, 1), better: cmp(o.goals_against_10, b.goals_against_10) },
    { label: "Shots on target, last 10", b: num(b.sot_10, 1), o: num(o.sot_10, 1), better: cmp(b.sot_10, o.sot_10) },
    { label: "Season points per game", b: num(b.points_per_game_season, 2), o: num(o.points_per_game_season, 2), better: cmp(b.points_per_game_season, o.points_per_game_season) },
    { label: "Days of rest", b: num(b.days_rest, 0), o: num(o.days_rest, 0), better: null },
  ];
  return (
    <Panel title="Team comparison" subtitle="Going into the match">
      <div className="mb-4 grid grid-cols-[1fr_auto_1fr] items-center gap-3 text-sm">
        <FormRow form={b.form} />
        <span className="text-xs text-muted-foreground">form</span>
        <div className="flex justify-end"><FormRow form={o.form} /></div>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-muted-foreground">
            <th className="pb-2 text-left font-medium"><span className="mr-1.5 inline-block h-2 w-2 rounded-full" style={{ background: colors.barca }} />Barcelona</th>
            <th className="pb-2 font-medium" />
            <th className="pb-2 text-right font-medium">{o.team.short_name}<span className="ml-1.5 inline-block h-2 w-2 rounded-full" style={{ background: colors.opponent }} /></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label} className="border-t border-border">
              <td className={`py-2 tabular ${r.better === "b" ? "font-semibold" : "text-muted-foreground"}`}>{r.b}</td>
              <td className="py-2 text-center text-xs text-muted-foreground">{r.label}</td>
              <td className={`py-2 text-right tabular ${r.better === "o" ? "font-semibold" : "text-muted-foreground"}`}>{r.o}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

const cmp = (a?: number | null, b?: number | null): "b" | "o" | null => (a == null || b == null || a === b ? null : a > b ? "b" : "o");

function FormRow({ form }: { form: string[] }) {
  return <div className="flex gap-1">{form.map((r, i) => <ResultChip key={i} result={r} size="sm" />)}</div>;
}

function GroupTotals({ groups, base, p }: { groups: Record<string, number>; base?: number | null; p: number }) {
  const items = Object.entries(groups).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
  return (
    <div className="rounded-lg bg-surface-2 p-4 text-xs">
      <p className="mb-2 font-medium text-muted-foreground">By feature group</p>
      <div className="grid grid-cols-2 gap-x-6 gap-y-1.5">
        {items.map(([g, v]) => (
          <div key={g} className="flex justify-between gap-2">
            <span className="truncate text-muted-foreground">{g}</span>
            <span className="tabular font-medium" style={{ color: v >= 0 ? "#4cc24c" : "#e06a6a" }}>{(v >= 0 ? "+" : "") + (v * 100).toFixed(1)}</span>
          </div>
        ))}
      </div>
      {base != null && (
        <p className="mt-3 text-muted-foreground">
          Average prediction {pct(base)} + contributions = <b className="text-foreground">{pct(p)}</b>
        </p>
      )}
    </div>
  );
}

function MatchAnalysis({ data }: { data: MatchDetail }) {
  const id = data.match.id;
  const shots = useShots(id);
  const passes = usePasses(id);
  const s = data.stats;
  const rows = useMemo(() => s ? ([
    ["Goals", s.barca.goals, s.opponent.goals, 0],
    ["Expected goals (xG)", s.barca.xg, s.opponent.xg, 2],
    ["Shots", s.barca.shots, s.opponent.shots, 0],
    ["Shots on target", s.barca.shots_on_target, s.opponent.shots_on_target, 0],
    ["Big chances", s.barca.big_chances, s.opponent.big_chances, 0],
    ["Possession", s.barca.possession, s.opponent.possession, -1],
    ["Passes", s.barca.passes, s.opponent.passes, 0],
    ["Pass completion", s.barca.pass_completion, s.opponent.pass_completion, -1],
    ["Progressive passes", s.barca.progressive_passes, s.opponent.progressive_passes, 0],
    ["Box entries", s.barca.box_entries, s.opponent.box_entries, 0],
    ["Pressures", s.barca.pressures, s.opponent.pressures, 0],
    ["PPDA (lower = more pressing)", s.barca.ppda, s.opponent.ppda, 1],
    ["Field tilt", s.barca.field_tilt, s.opponent.field_tilt, -1],
    ["Expected threat (xT)", s.barca.xt ?? 0, s.opponent.xt ?? 0, 2],
  ] as [string, number, number, number][]) : [], [s]);
  return (
    <Panel title="Match analysis" subtitle="What happened, from StatsBomb event data">
      <Tabs defaultValue="shots">
        <TabsList className="mb-4">
          <TabsTrigger value="shots">Shot map</TabsTrigger>
          <TabsTrigger value="network">Pass network</TabsTrigger>
          <TabsTrigger value="stats">Statistics</TabsTrigger>
        </TabsList>
        <TabsContent value="shots">
          {shots.data ? <ShotMap shots={shots.data} /> : <Loading className="h-80" />}
        </TabsContent>
        <TabsContent value="network">
          {passes.data ? <div className="mx-auto max-w-4xl"><PassNetwork net={passes.data} /></div> : <Loading className="h-80" />}
        </TabsContent>
        <TabsContent value="stats">
          <div className="mx-auto max-w-2xl space-y-2.5">
            {rows.map(([label, bv, ov, d]) => {
              const total = bv + ov || 1;
              const fmt = (v: number) => (d === -1 ? pct(v) : num(v, d));
              return (
                <div key={label}>
                  <div className="mb-1 flex justify-between text-sm">
                    <span className="tabular font-medium">{fmt(bv)}</span>
                    <span className="text-xs text-muted-foreground">{label}</span>
                    <span className="tabular font-medium">{fmt(ov)}</span>
                  </div>
                  <div className="flex h-1.5 gap-[2px]">
                    <div className="rounded-l-full" style={{ flexGrow: bv / total, background: colors.barca }} />
                    <div className="rounded-r-full" style={{ flexGrow: ov / total, background: colors.opponent }} />
                  </div>
                </div>
              );
            })}
            {!s && <Empty>No statistics recorded.</Empty>}
          </div>
        </TabsContent>
      </Tabs>
    </Panel>
  );
}
