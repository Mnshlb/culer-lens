"use client";

import Link from "next/link";
import { Meter, WORKLOAD_BANDS } from "@/components/charts/meter";
import { HeatmapLayer } from "@/components/pitch/heatmap-layer";
import { Pitch } from "@/components/pitch/pitch";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { type LineupPlayer, useHeatmap } from "@/lib/api";
import { num, pct } from "@/lib/format";
import { colors } from "@/lib/theme";

const FAMILY = { GK: "Goalkeeper", CB: "Centre-back", FB: "Full-back", MF: "Midfielder", AM: "Attacking midfielder / winger", FW: "Forward" } as const;

export function PlayerSheet({ player, date, onClose }: { player: LineupPlayer | null; date: string; onClose: () => void }) {
  return (
    <Sheet open={!!player} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto border-border bg-card sm:max-w-md">
        {player && <Body player={player} date={date} />}
      </SheetContent>
    </Sheet>
  );
}

function Body({ player, date }: { player: LineupPlayer; date: string }) {
  const heat = useHeatmap(player.player_id, { family: "touches", window: "last5", as_of: date });
  return (
    <div className="space-y-6 px-1 pb-8">
      <SheetHeader className="px-4 pt-6">
        <p className="text-xs uppercase tracking-[0.14em] text-primary">
          {FAMILY[player.position_family as keyof typeof FAMILY] ?? "Player"}
          {player.slot ? ` · ${player.slot}` : ""}
        </p>
        <SheetTitle className="text-2xl">{player.name}</SheetTitle>
        <SheetDescription>Everything here was known before kick-off.</SheetDescription>
      </SheetHeader>
      <div className="grid grid-cols-3 gap-3 px-4">
        <Box label="Start probability" value={pct(player.p_start)} accent />
        <Box label="Form" value={num(player.form_rating, 1)} sub="last 5 ratings" />
        <Box label="Workload" value={String(Math.round(player.workload_index))} sub={player.workload_band} />
      </div>
      <div className="px-4">
        <Meter value={player.workload_index} bands={WORKLOAD_BANDS} height={6} />
      </div>
      <div className="grid grid-cols-2 gap-3 px-4 text-sm">
        <Line label="Minutes per match, last 5" value={num(player.minutes_last5, 0)} />
        <Line label="Starts in last 5" value={num(player.starts_last5, 0)} />
      </div>
      <div className="px-4">
        <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Why selected?</p>
        <ul className="space-y-2">
          {player.reasons.map((r) => (
            <li key={r.feature} className="flex items-start gap-2.5 text-sm">
              <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-md text-xs font-bold text-white"
                    style={{ background: r.shap >= 0 ? colors.win : colors.loss }}>
                {r.shap >= 0 ? "+" : "−"}
              </span>
              <span>{r.text}</span>
            </li>
          ))}
          {player.reasons.length === 0 && <li className="text-sm text-muted-foreground">No explanation stored.</li>}
        </ul>
      </div>
      <div className="px-4">
        <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Touches, last five matches</p>
        <div className="rounded-lg bg-surface-2 p-2">
          <Pitch className="h-auto w-full" under={heat.data ? <HeatmapLayer grid={heat.data.grid} /> : null} />
        </div>
        <p className="mt-1.5 text-xs text-muted-foreground">
          {heat.data ? `${heat.data.events} touches in ${heat.data.matches} matches · attacking left to right` : heat.error ? "No earlier matches recorded." : "Loading…"}
        </p>
      </div>
      <div className="px-4">
        <Link href={`/players/${player.player_id}`} className="text-sm font-medium text-primary hover:underline">
          Full player profile →
        </Link>
      </div>
    </div>
  );
}

function Box({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: boolean }) {
  return (
    <div className="rounded-lg bg-surface-2 p-3">
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p className={`mt-1 text-2xl font-semibold ${accent ? "text-primary" : ""}`}>{value}</p>
      {sub && <p className="text-[11px] text-muted-foreground">{sub}</p>}
    </div>
  );
}

function Line({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between rounded-md border border-border px-3 py-2">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="font-semibold tabular">{value}</span>
    </div>
  );
}
