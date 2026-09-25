"use client";

import { heat } from "@/lib/theme";
import { project, type Orientation } from "./pitch";

const THIRD_EDGES = [0, 40, 80, 120];
const CHANNEL_EDGES = [0, 18, 30, 50, 62, 80];
export const THIRDS = ["defensive", "middle", "attacking"] as const;
export const CHANNELS = ["left_wing", "left_half_space", "centre", "right_half_space", "right_wing"] as const;

/** Density grid from the API (grid[i][j]: i along the pitch, j across), normalised to its maximum. */
export function HeatmapLayer({ grid, orientation = "horizontal", smooth = 1.1 }: { grid: number[][]; orientation?: Orientation; smooth?: number }) {
  const p = project(orientation);
  const id = `hm-${orientation}`;
  const [w0, h0] = orientation === "horizontal" ? [120, 80] : [80, 120];
  const nx = grid.length;
  const ny = grid[0]?.length ?? 0;
  const max = Math.max(1e-9, ...grid.flat());
  const w = 120 / nx;
  const h = 80 / ny;
  return (
    <g>
      <defs>
        <filter id={`${id}-blur`} x="-5%" y="-5%" width="110%" height="110%">
          <feGaussianBlur stdDeviation={smooth} />
        </filter>
        <clipPath id={`${id}-clip`}>
          <rect x={0} y={0} width={w0} height={h0} />
        </clipPath>
      </defs>
      <g clipPath={`url(#${id}-clip)`} filter={smooth > 0 ? `url(#${id}-blur)` : undefined}>
      {grid.flatMap((col, i) =>
        col.map((v, j) => {
          if (v <= 0) return null;
          const [ax, ay] = p(i * w, j * h);
          const [bx, by] = p((i + 1) * w, (j + 1) * h);
          return (
            <rect key={`${i}-${j}`} x={Math.min(ax, bx)} y={Math.min(ay, by)} width={Math.abs(bx - ax) + 0.05}
                  height={Math.abs(by - ay) + 0.05} fill={heat(v / max)} />
          );
        }),
      )}
      </g>
    </g>
  );
}

export function ZoneOverlay({
  selected,
  onSelect,
  orientation = "horizontal",
}: {
  selected?: string | null;
  onSelect: (key: string) => void;
  orientation?: Orientation;
}) {
  const p = project(orientation);
  return (
    <g>
      {THIRDS.map((t, i) =>
        CHANNELS.map((c, j) => {
          const [ax, ay] = p(THIRD_EDGES[i], CHANNEL_EDGES[j]);
          const [bx, by] = p(THIRD_EDGES[i + 1], CHANNEL_EDGES[j + 1]);
          const key = `${t}:${c}`;
          const active = selected === key;
          return (
            <rect
              key={key}
              x={Math.min(ax, bx)}
              y={Math.min(ay, by)}
              width={Math.abs(bx - ax)}
              height={Math.abs(by - ay)}
              fill={active ? "rgba(255,255,255,0.10)" : "transparent"}
              stroke={active ? "rgba(255,255,255,0.75)" : "rgba(255,255,255,0.06)"}
              strokeWidth={active ? 0.5 : 0.25}
              className="cursor-pointer transition-colors hover:fill-white/5"
              onClick={() => onSelect(key)}
              aria-label={`${t} third, ${c.replaceAll("_", " ")}`}
            />
          );
        }),
      )}
    </g>
  );
}

export const zoneLabel = (key: string) => {
  const [t, c] = key.split(":");
  const channel = c.replaceAll("_", " ").replace("half space", "half-space");
  return `${channel[0].toUpperCase()}${channel.slice(1)}, ${t} third`;
};
