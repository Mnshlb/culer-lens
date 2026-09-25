"use client";

import { useState } from "react";
import { CHANNELS, HeatmapLayer, THIRDS, ZoneOverlay, zoneLabel } from "@/components/pitch/heatmap-layer";
import { Pitch } from "@/components/pitch/pitch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { type Heatmap, type PlayerMatchRow, useHeatmap } from "@/lib/api";
import { date as fmtDate, pct } from "@/lib/format";

const FAMILIES = [
  ["all", "All actions"], ["touches", "Touches"], ["passes", "Passing"], ["carries", "Carries"],
  ["attacking", "Attacking"], ["defending", "Defending"],
] as const;
const WINDOWS = [["match", "Match"], ["last5", "Last 5"], ["last10", "Last 10"], ["season", "Season"]] as const;

type Filters = { family: string; window: string; season?: string; match_id?: number };

export function HeatmapExplorer({ playerId, seasons, matches }: { playerId: number; seasons: string[]; matches: PlayerMatchRow[] }) {
  const [compare, setCompare] = useState(false);
  const [a, setA] = useState<Filters>({ family: "all", window: "season", season: seasons.at(-1) });
  const [b, setB] = useState<Filters>({ family: "all", window: "match", match_id: matches[1]?.match_id });
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">Event heatmap: where the player did something recorded, not a physical coverage map.</p>
        <button onClick={() => setCompare((c) => !c)} className="text-xs font-medium text-primary hover:underline">
          {compare ? "Single view" : "Compare two views"}
        </button>
      </div>
      <div className={compare ? "grid gap-6 xl:grid-cols-2" : ""}>
        <View playerId={playerId} filters={a} onChange={setA} seasons={seasons} matches={matches} />
        {compare && <View playerId={playerId} filters={b} onChange={setB} seasons={seasons} matches={matches} />}
      </div>
    </div>
  );
}

function View({ playerId, filters, onChange, seasons, matches }: {
  playerId: number; filters: Filters; onChange: (f: Filters) => void; seasons: string[]; matches: PlayerMatchRow[];
}) {
  const { data } = useHeatmap(playerId, filters);
  const [zone, setZone] = useState<string | null>(null);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <ToggleGroup type="single" value={filters.family} onValueChange={(v) => v && onChange({ ...filters, family: v })}
                     className="flex-wrap rounded-md bg-surface-2 p-0.5">
          {FAMILIES.map(([k, label]) => <ToggleGroupItem key={k} value={k} className="h-7 px-2.5 text-xs">{label}</ToggleGroupItem>)}
        </ToggleGroup>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <ToggleGroup type="single" value={filters.window} onValueChange={(v) => v && onChange({ ...filters, window: v })}
                     className="rounded-md bg-surface-2 p-0.5">
          {WINDOWS.map(([k, label]) => <ToggleGroupItem key={k} value={k} className="h-7 px-2.5 text-xs">{label}</ToggleGroupItem>)}
        </ToggleGroup>
        {filters.window === "season" && (
          <Select value={filters.season} onValueChange={(v) => onChange({ ...filters, season: v })}>
            <SelectTrigger className="h-8 w-[120px] bg-surface-2 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>{[...seasons].reverse().map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
          </Select>
        )}
        {filters.window === "match" && (
          <Select value={filters.match_id ? String(filters.match_id) : undefined} onValueChange={(v) => onChange({ ...filters, match_id: Number(v) })}>
            <SelectTrigger className="h-8 w-[220px] bg-surface-2 text-xs"><SelectValue placeholder="Latest match" /></SelectTrigger>
            <SelectContent className="max-h-72">
              {matches.map((m) => (
                <SelectItem key={m.match_id} value={String(m.match_id)}>
                  {fmtDate(m.date, { day: "2-digit", month: "short", year: "2-digit" })} · {m.barca_home ? "vs" : "at"} {m.opponent}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>
      <div className="grid gap-4 md:grid-cols-[1fr_200px]">
        <div className="rounded-xl bg-surface-2 p-2">
          <Pitch className="h-auto w-full" under={data ? <HeatmapLayer grid={data.grid} /> : null}>
            <ZoneOverlay selected={zone} onSelect={(k) => setZone((z) => (z === k ? null : k))} />
          </Pitch>
          <p className="px-1 pt-1.5 text-[11px] text-muted-foreground">
            {data ? `${data.events.toLocaleString()} actions · ${data.matches} match${data.matches === 1 ? "" : "es"} · attacking left to right · click a zone` : "Loading…"}
          </p>
        </div>
        <ZonePanel data={data} zone={zone} />
      </div>
    </div>
  );
}

function ZonePanel({ data, zone }: { data?: Heatmap; zone: string | null }) {
  if (!data) return null;
  const s = data.summary;
  if (zone) {
    const [t, c] = zone.split(":");
    const z = data.zones.find((x) => x.third === t && x.channel === c);
    const entries = Object.entries(z?.breakdown ?? {}).sort((a, b) => b[1] - a[1]);
    return (
      <div className="space-y-3 text-sm">
        <p className="font-medium">{zoneLabel(zone)}</p>
        <div className="flex items-baseline justify-between border-b border-border pb-2">
          <span className="text-muted-foreground">Actions</span><span className="text-lg font-semibold tabular">{z?.total ?? 0}</span>
        </div>
        {entries.map(([k, v]) => (
          <div key={k} className="flex justify-between"><span className="capitalize text-muted-foreground">{k}</span><span className="tabular">{v}</span></div>
        ))}
        <p className="text-xs text-muted-foreground">{pct((z?.total ?? 0) / Math.max(1, data.events))} of the player&apos;s actions in this view.</p>
      </div>
    );
  }
  const channel = (k: string) => s[k] as number | null;
  return (
    <div className="space-y-3 text-sm">
      <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Spatial profile</p>
      {[["Defensive third", "defensive_third"], ["Middle third", "middle_third"], ["Attacking third", "attacking_third"]].map(([l, k]) => (
        <Row key={k} label={l} value={pct(channel(k))} />
      ))}
      <div className="border-t border-border pt-2" />
      {[["Left", "left"], ["Centre", "centre"], ["Right", "right"], ["In the box", "box_share"]].map(([l, k]) => (
        <Row key={k} label={l} value={pct(channel(k))} />
      ))}
      <p className="text-[11px] text-muted-foreground">Left/right from Barcelona&apos;s attacking direction (wing + half-space). {THIRDS.length * CHANNELS.length} zones.</p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return <div className="flex justify-between"><span className="text-muted-foreground">{label}</span><span className="font-medium tabular">{value}</span></div>;
}
