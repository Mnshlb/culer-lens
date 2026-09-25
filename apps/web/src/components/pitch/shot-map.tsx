"use client";

import { useState } from "react";
import type { Shot } from "@/lib/api";
import { colors } from "@/lib/theme";
import { Pitch } from "./pitch";

/** Barcelona attack right, the opponent left (mirrored by the API). Area ∝ xG; goals filled. */
export function ShotMap({ shots }: { shots: Shot[] }) {
  const [hover, setHover] = useState<Shot | null>(null);
  const radius = (xg: number) => 0.9 + Math.sqrt(xg) * 4.2;
  return (
    <div className="relative">
      <Pitch className="h-auto w-full">
        {shots.map((s, i) => {
          const c = s.team === "barca" ? colors.barca : colors.opponent;
          return (
            <circle
              key={i}
              cx={s.x}
              cy={s.y}
              r={radius(s.xg)}
              fill={s.goal ? c : "transparent"}
              fillOpacity={s.goal ? 0.95 : 0}
              stroke={s.goal ? colors.surface : c}
              strokeWidth={s.goal ? 0.4 : 0.45}
              className="cursor-pointer"
              onMouseEnter={() => setHover(s)}
              onMouseLeave={() => setHover(null)}
            />
          );
        })}
      </Pitch>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <div className="flex items-center gap-4">
          <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: colors.barca }} />Barcelona →</span>
          <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: colors.opponent }} />← Opponent</span>
          <span>filled = goal · size = xG</span>
        </div>
        <span className="min-h-4 text-foreground">
          {hover ? `${hover.minute}' ${hover.player ?? ""} · xG ${hover.xg.toFixed(2)} · ${hover.outcome ?? ""}` : "Hover a shot"}
        </span>
      </div>
    </div>
  );
}
