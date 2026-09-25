"use client";

import type { PassNetwork as Net } from "@/lib/api";
import { surname } from "@/lib/format";
import { colors } from "@/lib/theme";
import { Pitch } from "./pitch";

export function PassNetwork({ net }: { net: Net }) {
  const pos = new Map(net.nodes.map((n) => [n.player_id, n]));
  const maxEdge = Math.max(1, ...net.edges.map((e) => e.count));
  const maxPasses = Math.max(1, ...net.nodes.map((n) => n.passes));
  return (
    <div>
      <Pitch className="h-auto w-full">
        {net.edges.map((e, i) => {
          const a = pos.get(e.source);
          const b = pos.get(e.target);
          if (!a || !b) return null;
          return (
            <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={colors.barca}
                  strokeOpacity={0.15 + 0.6 * (e.count / maxEdge)} strokeWidth={0.3 + 1.6 * (e.count / maxEdge)}
                  strokeLinecap="round" />
          );
        })}
        {net.nodes.map((n) => (
          <g key={n.player_id}>
            <circle cx={n.x} cy={n.y} r={1.3 + 2.4 * Math.sqrt(n.passes / maxPasses)} fill={colors.barca}
                    stroke={colors.pitch} strokeWidth={0.5} />
            <text x={n.x} y={n.y + 5.2} textAnchor="middle" fontSize={2.6} fill={colors.ink}>{surname(n.name)}</text>
          </g>
        ))}
      </Pitch>
      <p className="mt-2 text-xs text-muted-foreground">
        Average position of each player&apos;s completed passes and receptions until the first substitution
        ({net.until_minute}&apos;). Links = at least 3 completed passes between the pair; thicker = more.
      </p>
    </div>
  );
}
