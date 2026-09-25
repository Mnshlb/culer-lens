"use client";

import { motion } from "motion/react";
import { colors } from "@/lib/theme";

type C = { feature: string; label: string; value: number | null; shap: number };

const fmt = (v: number | null) => {
  if (v == null) return "–";
  if (Math.abs(v) >= 100) return Math.round(v).toString();
  if (Math.abs(v) < 1) return v.toFixed(2);
  return v.toFixed(1);
};

/** SHAP contributions to P(win), diverging from zero: green pushes towards a win, red away from it. */
export function Contributions({ items, max = 8, compact = false }: { items: C[]; max?: number; compact?: boolean }) {
  const rows = items.slice(0, max);
  const scale = Math.max(0.02, ...rows.map((r) => Math.abs(r.shap)));
  if (compact) {
    return (
      <div className="space-y-2.5">
        {rows.map((r, i) => {
          const pos = r.shap >= 0;
          return (
            <div key={r.feature} className="text-xs">
              <div className="mb-1 flex items-baseline justify-between gap-3">
                <span className="text-muted-foreground">{r.label}</span>
                <span className="shrink-0 font-medium tabular">{(pos ? "+" : "") + (r.shap * 100).toFixed(1)} pp</span>
              </div>
              <div className="h-1.5 rounded-full bg-white/5">
                <motion.div initial={{ width: 0 }} animate={{ width: `${(Math.abs(r.shap) / scale) * 100}%` }}
                            transition={{ duration: 0.5, delay: i * 0.04 }} className="h-full rounded-full"
                            style={{ background: pos ? colors.win : colors.loss }} />
              </div>
            </div>
          );
        })}
      </div>
    );
  }
  return (
    <div className="space-y-1.5">
      {rows.map((r, i) => {
        const w = (Math.abs(r.shap) / scale) * 50;
        const pos = r.shap >= 0;
        return (
          <div key={r.feature} className="grid grid-cols-[minmax(0,1fr)_160px_52px] items-center gap-3 text-xs">
            <div className="truncate text-muted-foreground" title={r.label}>
              {r.label} <span className="text-foreground/90 tabular">({fmt(r.value)})</span>
            </div>
            <div className="relative h-4">
              <div className="absolute inset-y-0 left-1/2 w-px bg-white/15" />
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${w}%` }}
                transition={{ duration: 0.5, delay: i * 0.03 }}
                className="absolute top-1/2 h-2.5 -translate-y-1/2"
                style={{
                  background: pos ? colors.win : colors.loss,
                  left: pos ? "50%" : undefined,
                  right: pos ? undefined : "50%",
                  borderRadius: pos ? "0 4px 4px 0" : "4px 0 0 4px",
                }}
              />
            </div>
            <div className="text-right font-medium tabular">{(r.shap > 0 ? "+" : "") + (r.shap * 100).toFixed(1)}</div>
          </div>
        );
      })}
      <p className="pt-1 text-[11px] text-muted-foreground">Percentage points of P(Barcelona win) each input adds (+) or removes (−) relative to the average prediction.</p>
    </div>
  );
}

export function Bars({ items, unit = "", color = colors.barca }: { items: { label: string; value: number; sub?: string }[]; unit?: string; color?: string }) {
  const max = Math.max(1e-9, ...items.map((i) => i.value));
  return (
    <div className="space-y-2">
      {items.map((it) => (
        <div key={it.label} className="grid grid-cols-[minmax(0,180px)_1fr_64px] items-center gap-3 text-xs">
          <div className="truncate text-muted-foreground" title={it.label}>{it.label}</div>
          <div className="h-2.5 rounded-r-[4px] bg-white/5">
            <div className="h-full rounded-r-[4px]" style={{ width: `${Math.max(0, (it.value / max) * 100)}%`, background: color }} />
          </div>
          <div className="text-right font-medium tabular">{it.value.toFixed(it.value < 0.1 ? 3 : 2)}{unit}</div>
        </div>
      ))}
    </div>
  );
}
