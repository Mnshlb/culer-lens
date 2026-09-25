"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { ErrorState, Loading, PageTitle, Panel } from "@/components/common/ui";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { usePlayers, useSeasons } from "@/lib/api";
import { int, num } from "@/lib/format";

const FAMILIES = ["All", "GK", "CB", "FB", "MF", "AM", "FW"];

export function PlayerList({ season }: { season?: string }) {
  const router = useRouter();
  const seasons = useSeasons();
  const current = season ?? seasons.data?.at(-1)?.label;
  const players = usePlayers(current, 1);
  const [query, setQuery] = useState("");
  const [family, setFamily] = useState("All");
  const rows = useMemo(
    () => (players.data ?? []).filter((p) =>
      (family === "All" || p.position_family === family) && p.name.toLowerCase().includes(query.toLowerCase())),
    [players.data, family, query],
  );
  return (
    <div>
      <PageTitle eyebrow="Players" title="Squad and ratings">
        <Select value={current} onValueChange={(v) => router.push(`/players?season=${encodeURIComponent(v)}`)}>
          <SelectTrigger className="h-9 w-[140px] bg-card"><SelectValue placeholder="Season" /></SelectTrigger>
          <SelectContent>
            {[...(seasons.data ?? [])].reverse().map((s) => <SelectItem key={s.label} value={s.label}>{s.label}</SelectItem>)}
          </SelectContent>
        </Select>
      </PageTitle>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search players" className="h-9 w-56 bg-card pl-8" />
        </div>
        <ToggleGroup type="single" value={family} onValueChange={(v) => v && setFamily(v)} className="rounded-md bg-card p-0.5">
          {FAMILIES.map((f) => <ToggleGroupItem key={f} value={f} className="h-8 px-3 text-xs">{f}</ToggleGroupItem>)}
        </ToggleGroup>
      </div>
      {players.error ? <ErrorState error={players.error} /> : !players.data ? <Loading className="h-[60vh]" /> : (
        <Panel bodyClassName="p-0">
          <table className="w-full text-sm">
            <thead className="border-b border-border text-xs text-muted-foreground">
              <tr>
                <th className="px-5 py-3 text-left font-medium">Player</th>
                <th className="px-3 py-3 text-left font-medium">Pos</th>
                <th className="px-3 py-3 text-right font-medium">Apps</th>
                <th className="px-3 py-3 text-right font-medium">Minutes</th>
                <th className="px-3 py-3 text-right font-medium">Goals</th>
                <th className="px-3 py-3 text-right font-medium">Assists</th>
                <th className="px-5 py-3 text-right font-medium">Rating</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.id} onClick={() => router.push(`/players/${p.id}`)}
                    className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-secondary/60">
                  <td className="px-5 py-2.5 font-medium">{p.name}</td>
                  <td className="px-3 py-2.5 text-muted-foreground">{p.position_family ?? "–"}</td>
                  <td className="px-3 py-2.5 text-right tabular">{p.appearances}</td>
                  <td className="px-3 py-2.5 text-right tabular">{int(p.minutes)}</td>
                  <td className="px-3 py-2.5 text-right tabular">{p.goals}</td>
                  <td className="px-3 py-2.5 text-right tabular">{p.assists}</td>
                  <td className="px-5 py-2.5 text-right">
                    {p.overall != null && p.minutes >= 900 ? (
                      <span className="inline-flex items-center gap-2">
                        <span className="h-1.5 w-16 overflow-hidden rounded-full bg-white/5">
                          <span className="block h-full rounded-full bg-primary" style={{ width: `${p.overall}%` }} />
                        </span>
                        <span className="w-8 font-semibold tabular">{num(p.overall, 0)}</span>
                      </span>
                    ) : <span className="text-xs text-muted-foreground">{p.position_family === "GK" ? "not rated" : "< 900 min"}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}
      <p className="mt-3 text-xs text-muted-foreground">
        Rating = BIPR overall (0-100): the player&apos;s position-weighted percentile profile against every La Liga player of
        the same position family in 2015/16. Shown from 900 minutes. Goalkeepers are not rated.
      </p>
    </div>
  );
}
