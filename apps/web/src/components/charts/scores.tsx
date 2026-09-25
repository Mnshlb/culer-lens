"use client";

import { pct } from "@/lib/format";
import { colors } from "@/lib/theme";

export function ScoreList({ scores, actual }: { scores: { barca: number; opponent: number; p: number }[]; actual?: [number, number] }) {
  const max = Math.max(...scores.map((s) => s.p), 1e-9);
  return (
    <div className="space-y-1.5">
      {scores.slice(0, 6).map((s) => {
        const hit = actual && actual[0] === s.barca && actual[1] === s.opponent;
        return (
          <div key={`${s.barca}-${s.opponent}`} className="grid grid-cols-[88px_1fr_48px] items-center gap-3 text-sm">
            <span className="tabular text-muted-foreground">
              Barça <span className="font-semibold text-foreground">{s.barca}-{s.opponent}</span>
            </span>
            <div className="h-2 rounded-r-[4px] bg-white/5">
              <div className="h-full rounded-r-[4px]" style={{ width: `${(s.p / max) * 100}%`, background: hit ? colors.win : colors.barca }} />
            </div>
            <span className="text-right text-xs tabular">{pct(s.p, 1)}</span>
          </div>
        );
      })}
    </div>
  );
}
