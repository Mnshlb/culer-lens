"use client";

import { motion } from "motion/react";
import { pct } from "@/lib/format";
import { colors } from "@/lib/theme";

type P = { win: number; draw: number; loss: number };

/** Win/draw/loss as one horizontal bar with a 2px gap between segments; labels outside the bar. */
export function ProbabilityBar({ p, market, labels }: { p: P; market?: P | null; labels?: [string, string, string] }) {
  const parts = [
    { key: "win", v: p.win, c: colors.win, label: labels?.[0] ?? "Win" },
    { key: "draw", v: p.draw, c: colors.draw, label: labels?.[1] ?? "Draw" },
    { key: "loss", v: p.loss, c: colors.loss, label: labels?.[2] ?? "Loss" },
  ];
  return (
    <div className="space-y-2">
      <div className="flex h-3 w-full gap-[2px] overflow-hidden rounded-full">
        {parts.map((s, i) => (
          <motion.div
            key={s.key}
            initial={{ flexGrow: 0.0001 }}
            animate={{ flexGrow: s.v }}
            transition={{ duration: 0.7, delay: 0.05 * i, ease: [0.22, 1, 0.36, 1] }}
            style={{ background: s.c, flexBasis: 0 }}
            className="h-full first:rounded-l-full last:rounded-r-full"
          />
        ))}
      </div>
      <div className="grid grid-cols-3 text-xs">
        {parts.map((s, i) => (
          <div key={s.key} className={i === 1 ? "text-center" : i === 2 ? "text-right" : ""}>
            <span className="inline-flex items-center gap-1.5 text-muted-foreground">
              <span className="h-2 w-2 rounded-full" style={{ background: s.c }} />
              {s.label}
            </span>
            <span className="ml-1.5 font-semibold tabular text-foreground">{pct(s.v)}</span>
            {market && (
              <div className="text-[11px] text-muted-foreground/80 tabular">
                market {pct(market[s.key as keyof P])}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
