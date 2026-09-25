"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { TrendChart } from "@/components/charts/line-charts";
import { Meter, WORKLOAD_BANDS } from "@/components/charts/meter";
import { Radar } from "@/components/charts/radar";
import { ErrorState, InfoTip, Loading, Panel, ResultChip, Stat } from "@/components/common/ui";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { usePlayer, usePlayerStats, useWorkload } from "@/lib/api";
import { date as fmtDate, int, num, seasonShort } from "@/lib/format";
import { bandColor, colors } from "@/lib/theme";
import { HeatmapExplorer } from "./heatmap-explorer";

const PILLARS = ["passing", "creation", "progression", "carrying", "defending", "shooting", "security"];
const FAMILY: Record<string, string> = { GK: "Goalkeeper", CB: "Centre-back", FB: "Full-back", MF: "Midfielder", AM: "Attacking midfielder / winger", FW: "Forward" };

export function PlayerProfile({ id }: { id: number }) {
  const { data, error, isLoading } = usePlayer(id);
  const [season, setSeason] = useState<string | undefined>();
  const seasons = useMemo(() => data?.seasons ?? [], [data]);
  const rated = seasons.filter((s) => s.reliable && s.overall != null);
  const current = season ?? rated.at(-1)?.season ?? seasons.at(-1)?.season;
  const stats = usePlayerStats(id, current);
  const workload = useWorkload(id, current);
  if (error) return <ErrorState error={error} />;
  if (isLoading || !data) return <Loading className="h-[80vh]" />;

  const sr = seasons.find((s) => s.season === current);
  const latestRated = rated.at(-1);
  const form = data.form.length ? data.form.reduce((a, b) => a + b, 0) / data.form.length : null;
  const series = (stats.data ?? []).map((r) => ({
    label: fmtDate(r.date, { day: "numeric", month: "short" }),
    rating: r.match_rating,
    xg: r.xg,
    xa: r.xa,
    progressive: r.progressive_passes + r.progressive_carries,
  }));

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-border bg-card p-5 md:p-8">
        <p className="text-xs font-medium uppercase tracking-[0.14em] text-primary">
          {FAMILY[data.position_family ?? ""] ?? "Player"}{data.country ? ` · ${data.country}` : ""}
        </p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight md:text-4xl">{data.display_name}</h1>
        {data.name !== data.display_name && <p className="text-sm text-muted-foreground">{data.name}</p>}
        <div className="rule-blaugrana mt-4 w-40" />
        <div className="mt-6 grid grid-cols-2 gap-6 md:grid-cols-6">
          <Stat label="Minutes (La Liga)" value={int(data.totals.minutes)} sub={`${int(data.totals.appearances)} apps · ${int(data.totals.starts)} starts`} />
          <Stat label="Rating" value={latestRated ? num(latestRated.overall, 0) : "–"} sub={latestRated ? `BIPR ${latestRated.season}` : data.position_family === "GK" ? "goalkeepers not rated" : "fewer than 900 min"} />
          <Stat label="Form" value={num(form, 1)} sub="avg of last 5 match ratings" />
          <Stat label="Workload" value={data.workload ? int(data.workload.index as number) : "–"} sub={data.workload ? `${data.workload.band} · before ${fmtDate(String(data.workload.date))}` : undefined} />
          <Stat label="Goals" value={int(data.totals.goals)} sub={`xG ${num(data.totals.xg, 1)}`} />
          <Stat label="Assists" value={int(data.totals.assists)} sub={`xA ${num(data.totals.xa, 1)}`} />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground">Season</span>
        <Select value={current} onValueChange={setSeason}>
          <SelectTrigger className="h-9 w-[140px] bg-card"><SelectValue /></SelectTrigger>
          <SelectContent>{[...seasons].reverse().map((s) => <SelectItem key={s.season} value={s.season}>{s.season}</SelectItem>)}</SelectContent>
        </Select>
        {sr && <span className="text-xs text-muted-foreground">{sr.appearances} apps · {int(sr.minutes)} min{sr.reliable ? "" : " · below 900 minutes, rating not shown"}</span>}
      </div>

      <div className="grid gap-4 lg:grid-cols-[380px_1fr]">
        <Panel title="Performance profile" subtitle="BIPR pillars, percentile within position family"
               action={<InfoTip>Each pillar averages the player&apos;s percentiles on 2-5 per-90 metrics against every La Liga player of the same position family in 2015/16 (≥ 900 min). The overall score weights the pillars by position. A methodology, not an objective truth.</InfoTip>}>
          {sr?.reliable && sr.pillars ? (
            <div className="flex flex-col items-center">
              <Radar axes={PILLARS} series={[{ name: current ?? "", values: sr.pillars as Record<string, number>, color: colors.barca }]} />
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-sm text-muted-foreground">Overall</span>
                <span className="text-3xl font-semibold">{num(sr.overall, 0)}</span>
              </div>
            </div>
          ) : (
            <p className="py-12 text-center text-sm text-muted-foreground">
              {data.position_family === "GK" ? "Goalkeepers are not rated: shot-stopping needs post-shot xG, which the open data lacks." : "Not enough minutes this season for a reliable rating (900 needed)."}
            </p>
          )}
        </Panel>
        <Panel title="Trends" subtitle={`Match by match, ${current ?? ""}`}>
          {stats.data ? (
            <div className="grid gap-6 md:grid-cols-2">
              <div>
                <p className="mb-1 text-xs text-muted-foreground">Match rating (6.5 = median performance)</p>
                <TrendChart data={series} xKey="label" series={[{ key: "rating", name: "Rating", color: colors.barca }]} yDomain={[3, 10]} reference={6.5} />
              </div>
              <div>
                <p className="mb-1 text-xs text-muted-foreground">Chances: xG and xA per match</p>
                <TrendChart data={series} xKey="label" series={[{ key: "xg", name: "xG", color: colors.barca }, { key: "xa", name: "xA", color: colors.opponent }]} />
              </div>
              <div className="md:col-span-2">
                <p className="mb-1 text-xs text-muted-foreground">Progressive passes + carries per match</p>
                <TrendChart data={series} xKey="label" series={[{ key: "progressive", name: "Progressive actions", color: colors.opponent }]} height={180} />
              </div>
            </div>
          ) : <Loading className="h-64" />}
        </Panel>
      </div>

      <Panel title="Spatial profile" subtitle="Interactive event heatmap">
        {stats.data ? (
          <HeatmapExplorer playerId={id} seasons={seasons.map((s) => s.season)} matches={[...(stats.data ?? [])].reverse()} />
        ) : <Loading className="h-80" />}
      </Panel>

      <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <Panel title="Workload" subtitle="Index before each fixture (observed league minutes)"
               action={<InfoTip>Not a fatigue measure. 0-100 from minutes in the last 7/14/30 days, consecutive starts and rest; cup and European minutes are not in the data.</InfoTip>}>
          {workload.data && workload.data.series.length > 0 ? (
            <div className="space-y-5">
              <TrendChart
                data={workload.data.series.map((w) => ({ label: fmtDate(w.date, { day: "numeric", month: "short" }), index: w.workload_index, m14: w.minutes_14d }))}
                xKey="label" series={[{ key: "index", name: "Workload index", color: colors.third }]} yDomain={[0, 100]} height={200} />
              {workload.data.latest_components && (
                <div>
                  <p className="mb-2 text-xs text-muted-foreground">Latest index, by component</p>
                  <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-sm md:grid-cols-3">
                    {Object.entries(workload.data.latest_components).map(([k, v]) => (
                      <div key={k} className="flex justify-between"><span className="text-muted-foreground">{k.replaceAll("_", " ")}</span><span className="tabular font-medium">{num(v, 1)}</span></div>
                    ))}
                  </div>
                  {(() => {
                    const last = workload.data.series.at(-1)!;
                    return (
                      <div className="mt-4">
                        <div className="mb-1 flex justify-between text-xs"><span className="text-muted-foreground">Before {last.opponent}</span>
                          <span><span className="mr-1.5 inline-block h-2 w-2 rounded-full" style={{ background: bandColor[last.band] }} />{last.band} · <b>{Math.round(last.workload_index)}</b></span></div>
                        <Meter value={last.workload_index} bands={WORKLOAD_BANDS} height={6} />
                      </div>
                    );
                  })()}
                </div>
              )}
            </div>
          ) : <p className="text-sm text-muted-foreground">No workload records for this season.</p>}
        </Panel>
        <Panel title="Match history" subtitle={current} bodyClassName="p-0">
          <div className="max-h-[420px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-card text-xs text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="px-5 py-2 text-left font-medium">Match</th>
                  <th className="px-2 py-2 text-right font-medium">Min</th>
                  <th className="px-2 py-2 text-right font-medium">G</th>
                  <th className="px-2 py-2 text-right font-medium">A</th>
                  <th className="px-2 py-2 text-right font-medium">xG</th>
                  <th className="px-5 py-2 text-right font-medium">Rating</th>
                </tr>
              </thead>
              <tbody>
                {[...(stats.data ?? [])].reverse().map((r) => (
                  <tr key={r.match_id} className="border-b border-border/60">
                    <td className="px-5 py-2">
                      <Link href={`/matches/${r.match_id}`} className="flex items-center gap-2 hover:text-primary">
                        <ResultChip result={r.result} size="sm" />
                        <span className="text-xs text-muted-foreground tabular">{fmtDate(r.date, { day: "2-digit", month: "short" })}</span>
                        <span className="truncate">{r.barca_home ? "vs" : "at"} {r.opponent}</span>
                      </Link>
                    </td>
                    <td className="px-2 py-2 text-right tabular text-muted-foreground">{Math.round(r.minutes)}{r.started ? "" : "*"}</td>
                    <td className="px-2 py-2 text-right tabular">{r.goals || ""}</td>
                    <td className="px-2 py-2 text-right tabular">{r.assists || ""}</td>
                    <td className="px-2 py-2 text-right tabular text-muted-foreground">{num(r.xg, 2)}</td>
                    <td className="px-5 py-2 text-right font-semibold tabular">{num(r.match_rating, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="px-5 py-2 text-[11px] text-muted-foreground">* came off the bench · season {current ? seasonShort(current) : ""}</p>
        </Panel>
      </div>
    </div>
  );
}
