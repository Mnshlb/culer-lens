"use client";

import { motion } from "motion/react";
import type { LineupPlayer } from "@/lib/api";
import { surname } from "@/lib/format";
import { colors } from "@/lib/theme";
import { Pitch, project } from "./pitch";

/** Predicted XI on a vertical pitch; each player carries a ring showing P(start). */
export function LineupPitch({
  players,
  selected,
  onSelect,
  revealed,
}: {
  players: LineupPlayer[];
  selected?: number | null;
  onSelect: (p: LineupPlayer) => void;
  revealed?: boolean;
}) {
  const p = project("vertical");
  return (
    <Pitch orientation="vertical" className="h-auto w-full">
      {players.map((pl, i) => {
        if (pl.x == null || pl.y == null) return null;
        const [cx, cy] = p(pl.x, pl.y);
        const prob = pl.p_start ?? 0;
        const r = 4.2;
        const circ = 2 * Math.PI * (r + 1.1);
        const active = selected === pl.player_id;
        const wrong = revealed && pl.started === false;
        return (
          <motion.g
            key={pl.player_id}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.03 * i }}
            className="cursor-pointer"
            onClick={() => onSelect(pl)}
            role="button"
            aria-label={`${pl.name}, start probability ${Math.round(prob * 100)}%`}
          >
            <circle cx={cx} cy={cy} r={r + 1.1} fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth={0.7} />
            <circle cx={cx} cy={cy} r={r + 1.1} fill="none" stroke={colors.barca} strokeWidth={0.7}
                    strokeDasharray={`${circ * prob} ${circ}`} transform={`rotate(-90 ${cx} ${cy})`} strokeLinecap="round" />
            <circle cx={cx} cy={cy} r={r} fill={active ? colors.barca : "#1f2430"}
                    stroke={wrong ? colors.loss : active ? "#fff" : "rgba(255,255,255,0.25)"} strokeWidth={wrong ? 0.7 : 0.4} />
            <text x={cx} y={cy + 1.2} textAnchor="middle" fontSize={3.2} fontWeight={700} fill="#fff">
              {Math.round(prob * 100)}
            </text>
            <text x={cx} y={cy + r + 4.4} textAnchor="middle" fontSize={3} fill={colors.ink} fontWeight={500}>
              {surname(pl.name)}
            </text>
          </motion.g>
        );
      })}
    </Pitch>
  );
}
