"use client";

import { motion } from "motion/react";
import { colors } from "@/lib/theme";

type Series = { name: string; values: Record<string, number | null | undefined>; color: string };

/** Pillar radar, 0-100 on every axis. Axis labels carry the values of the first series. */
export function Radar({ axes, series, size = 300 }: { axes: string[]; series: Series[]; size?: number }) {
  const c = size / 2;
  const r = c - 60;
  const angle = (i: number) => (Math.PI * 2 * i) / axes.length - Math.PI / 2;
  const point = (i: number, v: number) => [c + Math.cos(angle(i)) * (r * v) / 100, c + Math.sin(angle(i)) * (r * v) / 100];
  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="h-auto w-full max-w-[360px]" role="img" aria-label="Pillar radar">
      {[25, 50, 75, 100].map((t) => (
        <polygon
          key={t}
          points={axes.map((_, i) => point(i, t).join(",")).join(" ")}
          fill="none"
          stroke={colors.grid}
          strokeWidth={1}
        />
      ))}
      {axes.map((a, i) => {
        const [x, y] = point(i, 100);
        const [lx, ly] = point(i, 122);
        const v = series[0]?.values[a];
        return (
          <g key={a}>
            <line x1={c} y1={c} x2={x} y2={y} stroke={colors.grid} />
            <text x={lx} y={ly - 4} textAnchor="middle" className="fill-muted-foreground" fontSize={10.5}>
              {a[0].toUpperCase() + a.slice(1)}
            </text>
            <text x={lx} y={ly + 9} textAnchor="middle" className="fill-foreground" fontSize={11} fontWeight={600}>
              {v == null ? "–" : Math.round(v)}
            </text>
          </g>
        );
      })}
      {series.map((s) => {
        const pts = axes.map((a, i) => point(i, s.values[a] ?? 0).join(",")).join(" ");
        return (
          <motion.polygon
            key={s.name}
            points={pts}
            initial={{ opacity: 0, scale: 0.6 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.6 }}
            style={{ transformOrigin: `${c}px ${c}px` }}
            fill={s.color}
            fillOpacity={0.14}
            stroke={s.color}
            strokeWidth={2}
            strokeLinejoin="round"
          />
        );
      })}
    </svg>
  );
}
