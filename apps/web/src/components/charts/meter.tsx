"use client";

import { motion } from "motion/react";

type Band = { from: number; to: number; label: string; color: string };

/** Horizontal 0-100 meter with labelled bands and a marker; the value is always printed. */
export function Meter({ value, bands, height = 8 }: { value: number; bands: Band[]; height?: number }) {
  const v = Math.max(0, Math.min(100, value));
  return (
    <div className="space-y-1.5">
      <div className="relative w-full" style={{ height }}>
        <div className="absolute inset-0 flex gap-[2px] overflow-hidden rounded-full">
          {bands.map((b) => (
            <div key={b.label} style={{ flexGrow: b.to - b.from, background: b.color, opacity: 0.28 }} className="h-full" />
          ))}
        </div>
        <motion.div
          className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-card"
          initial={{ left: "0%" }}
          animate={{ left: `${v}%` }}
          transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
          style={{ background: bands.find((b) => v >= b.from && v <= b.to)?.color ?? "#fff" }}
        />
      </div>
      <div className="flex text-[10px] uppercase tracking-wider text-muted-foreground">
        {bands.map((b) => (
          <div key={b.label} style={{ flexGrow: b.to - b.from }} className="truncate">
            {b.label}
          </div>
        ))}
      </div>
    </div>
  );
}

export const WORKLOAD_BANDS: Band[] = [
  { from: 0, to: 35, label: "Low", color: "#5b6170" },
  { from: 35, to: 60, label: "Moderate", color: "#3987e5" },
  { from: 60, to: 80, label: "Elevated", color: "#c98500" },
  { from: 80, to: 100, label: "High", color: "#e0457b" },
];

export const READINESS_BANDS: Band[] = [
  { from: 0, to: 50, label: "Stretched", color: "#d03b3b" },
  { from: 50, to: 70, label: "Fair", color: "#c98500" },
  { from: 70, to: 100, label: "Ready", color: "#0ca30c" },
];
