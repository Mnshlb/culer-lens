"use client";

import { useRouter } from "next/navigation";
import { useMemo } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useMatches, useSeasons } from "@/lib/api";
import { date as fmtDate } from "@/lib/format";

/** Time machine: choose any fixture and the page shows what the platform knew before it. */
export function AsOfPicker({ season, matchId, basePath = "/" }: { season?: string; matchId?: number; basePath?: string }) {
  const router = useRouter();
  const seasons = useSeasons();
  const matches = useMatches(season);
  const sorted = useMemo(() => [...(seasons.data ?? [])].reverse(), [seasons.data]);
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-muted-foreground">Viewing as of</span>
      <Select
        value={season}
        onValueChange={(v) => router.push(`${basePath}?season=${encodeURIComponent(v)}`)}
      >
        <SelectTrigger className="h-9 w-[132px] bg-card"><SelectValue placeholder="Season" /></SelectTrigger>
        <SelectContent>
          {sorted.map((s) => (
            <SelectItem key={s.label} value={s.label}>{s.label}</SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select
        value={matchId ? String(matchId) : undefined}
        onValueChange={(v) => {
          const m = matches.data?.find((x) => String(x.id) === v);
          if (m) router.push(`${basePath}?season=${encodeURIComponent(m.season)}&as_of=${m.date}`);
        }}
      >
        <SelectTrigger className="h-9 w-[260px] bg-card"><SelectValue placeholder="Fixture" /></SelectTrigger>
        <SelectContent className="max-h-80">
          {(matches.data ?? []).map((m) => (
            <SelectItem key={m.id} value={String(m.id)}>
              {fmtDate(m.date, { day: "2-digit", month: "short" })} · {m.barca_home ? "vs" : "at"} {m.opponent.short_name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
