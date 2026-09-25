"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { colors } from "@/lib/theme";

const axis = { stroke: colors.axis, tick: { fill: colors.muted, fontSize: 11 }, tickLine: false } as const;
const tooltipStyle = {
  contentStyle: { background: "#1a1e28", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, fontSize: 12 },
  labelStyle: { color: colors.ink },
  itemStyle: { color: colors.ink2 },
};

export type SeriesDef = { key: string; name: string; color: string };

export function TrendChart({ data, series, xKey, height = 240, yDomain, reference }: {
  data: Record<string, unknown>[];
  series: SeriesDef[];
  xKey: string;
  height?: number;
  yDomain?: [number | "auto", number | "auto"];
  reference?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={colors.grid} vertical={false} />
        <XAxis dataKey={xKey} {...axis} minTickGap={24} />
        <YAxis {...axis} domain={yDomain ?? ["auto", "auto"]} width={46} />
        {reference !== undefined && <ReferenceLine y={reference} stroke={colors.axis} />}
        <Tooltip {...tooltipStyle} />
        {series.length > 1 && <Legend wrapperStyle={{ fontSize: 12, color: colors.muted }} iconType="plainline" />}
        {series.map((s) => (
          <Line key={s.key} type="linear" dataKey={s.key} name={s.name} stroke={s.color} strokeWidth={2}
                dot={false} activeDot={{ r: 4, stroke: colors.surface, strokeWidth: 2 }} connectNulls isAnimationActive={false} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function Calibration({ series, height = 260 }: {
  series: { name: string; color: string; points: { predicted: number; observed: number; n: number }[] }[];
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ScatterChart margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={colors.grid} />
        <XAxis type="number" dataKey="predicted" domain={[0, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]} {...axis}
               tickFormatter={(v) => `${Math.round(v * 100)}%`} />
        <YAxis type="number" dataKey="observed" domain={[0, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]} {...axis}
               tickFormatter={(v) => `${Math.round(v * 100)}%`} width={46} />
        <ZAxis type="number" dataKey="n" range={[30, 30]} />
        <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke={colors.axis} />
        <Tooltip {...tooltipStyle} formatter={(v) => `${(Number(v) * 100).toFixed(1)}%`} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {series.map((s) => (
          <Scatter key={s.name} name={s.name} data={s.points} fill={s.color} line={{ stroke: s.color, strokeWidth: 2 }}
                   isAnimationActive={false} />
        ))}
      </ScatterChart>
    </ResponsiveContainer>
  );
}
