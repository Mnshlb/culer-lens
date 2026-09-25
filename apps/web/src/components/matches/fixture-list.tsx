"use client";

import { Eye, EyeOff } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { ErrorState, Loading, PageTitle, Panel, ResultChip, Stat } from "@/components/common/ui";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useMatches, useSeasons } from "@/lib/api";
import { date as fmtDate, num, pct } from "@/lib/format";
import { colors } from "@/lib/theme";

export function FixtureList({ season }: { season?: string }) {
  const router = useRouter();
  const seasons = useSeasons();
  const current = season ?? seasons.data?.at(-1)?.label;
  const matches = useMatches(current);
  const [revealed, setRevealed] = useState(false);

  const summary = useMemo(() => {
    const rows = (matches.data ?? []).filter((m) => m.prediction);
    const exp = rows.reduce((a, m) => a + 3 * m.prediction!.win + m.prediction!.draw, 0);
    const act = rows.reduce((a, m) => a + (m.result === "W" ? 3 : m.result === "D" ? 1 : 0), 0);
    const ll = rows.reduce((a, m) => {
      const p = m.result === "W" ? m.prediction!.win : m.result === "D" ? m.prediction!.draw : m.prediction!.loss;
      return a - Math.log(Math.max(p, 1e-9));
    }, 0) / Math.max(rows.length, 1);
    return { n: rows.length, exp, act, ll };
  }, [matches.data]);

  return (
    <div>
      <PageTitle eyebrow="Match Centre" title="Fixtures and pre-match predictions">
        <div className="flex items-center gap-2">
          <Select value={current} onValueChange={(v) => router.push(`/matches?season=${encodeURIComponent(v)}`)}>
            <SelectTrigger className="h-9 w-[140px] bg-card"><SelectValue placeholder="Season" /></SelectTrigger>
            <SelectContent>
              {[...(seasons.data ?? [])].reverse().map((s) => <SelectItem key={s.label} value={s.label}>{s.label}</SelectItem>)}
            </SelectContent>
          </Select>
          <Button variant="secondary" size="sm" className="h-9" onClick={() => setRevealed((r) => !r)}>
            {revealed ? <EyeOff className="mr-1.5 h-4 w-4" /> : <Eye className="mr-1.5 h-4 w-4" />}
            {revealed ? "Hide results" : "Reveal results"}
          </Button>
        </div>
      </PageTitle>
      {matches.error ? <ErrorState error={matches.error} /> : !matches.data ? <Loading className="h-[60vh]" /> : (
        <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
          <Panel bodyClassName="p-0">
            <table className="w-full text-sm">
              <thead className="border-b border-border text-xs text-muted-foreground">
                <tr>
                  <th className="px-5 py-3 text-left font-medium">Date</th>
                  <th className="px-3 py-3 text-left font-medium">Fixture</th>
                  <th className="hidden px-3 py-3 text-left font-medium md:table-cell">Pre-match W · D · L</th>
                  <th className="px-5 py-3 text-right font-medium">Result</th>
                </tr>
              </thead>
              <tbody>
                {matches.data.map((m) => (
                  <tr key={m.id} className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-secondary/60"
                      onClick={() => router.push(`/matches/${m.id}`)}>
                    <td className="whitespace-nowrap px-5 py-2.5 text-muted-foreground tabular">{fmtDate(m.date, { day: "2-digit", month: "short" })}</td>
                    <td className="px-3 py-2.5">
                      <Link href={`/matches/${m.id}`} className="font-medium hover:text-primary" onClick={(e) => e.stopPropagation()}>
                        {m.barca_home ? "Barcelona v " + m.opponent.name : m.opponent.name + " v Barcelona"}
                      </Link>
                      {m.competition !== "La Liga" && <span className="ml-2 rounded bg-surface-2 px-1.5 py-0.5 text-[10px] text-muted-foreground">{m.competition}</span>}
                    </td>
                    <td className="hidden px-3 py-2.5 md:table-cell">
                      {m.prediction ? (
                        <div className="flex items-center gap-3">
                          <div className="flex h-1.5 w-28 gap-[2px] overflow-hidden rounded-full">
                            <div style={{ flexGrow: m.prediction.win, background: colors.win }} />
                            <div style={{ flexGrow: m.prediction.draw, background: colors.draw }} />
                            <div style={{ flexGrow: m.prediction.loss, background: colors.loss }} />
                          </div>
                          <span className="text-xs tabular text-muted-foreground">
                            {pct(m.prediction.win)} · {pct(m.prediction.draw)} · {pct(m.prediction.loss)}
                          </span>
                        </div>
                      ) : <span className="text-xs text-muted-foreground">no prediction (final)</span>}
                    </td>
                    <td className="px-5 py-2.5 text-right">
                      {revealed ? (
                        <span className="inline-flex items-center gap-2">
                          <span className="tabular font-medium">{m.barca_goals}-{m.opponent_goals}</span>
                          <ResultChip result={m.result} size="sm" />
                        </span>
                      ) : <span className="text-xs text-muted-foreground">hidden</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
          <div className="space-y-4">
            <Panel title="Season in numbers" subtitle={current}>
              <div className="grid grid-cols-2 gap-4">
                <Stat label="Fixtures predicted" value={summary.n} />
                <Stat label="Model log loss" value={num(summary.ll, 3)} sub="lower is better" />
                <Stat label="Expected points" value={num(summary.exp, 1)} sub="Σ 3·P(W) + P(D)" />
                <Stat label="Actual points" value={revealed ? summary.act : "–"} sub={revealed ? `${summary.act - summary.exp >= 0 ? "+" : ""}${num(summary.act - summary.exp, 1)} vs model` : "reveal results"} />
              </div>
            </Panel>
            <Panel title="How to read this">
              <p className="text-sm leading-relaxed text-muted-foreground">
                Every probability was produced before kick-off by a model trained only on earlier seasons,
                exactly as it would have been on the day. Results stay hidden until you reveal them, so you can
                judge the predictions the way they were made.
              </p>
            </Panel>
          </div>
        </div>
      )}
    </div>
  );
}
