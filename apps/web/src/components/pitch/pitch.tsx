"use client";

import { colors } from "@/lib/theme";

export type Orientation = "horizontal" | "vertical";

/** Map StatsBomb coordinates (x along the pitch 0-120, y across 0-80, y = 0 is the attacking team's
 *  left) to SVG coordinates. Horizontal: attacking left → right. Vertical: attacking upwards. */
export function project(o: Orientation) {
  return o === "horizontal"
    ? (x: number, y: number): [number, number] => [x, y]
    : (x: number, y: number): [number, number] => [y, 120 - x];
}

function Markings({ o }: { o: Orientation }) {
  const p = project(o);
  const line = { stroke: colors.pitchLine, strokeWidth: 0.35, fill: "none" } as const;
  const rect = (x0: number, y0: number, x1: number, y1: number, key: string) => {
    const [ax, ay] = p(x0, y0);
    const [bx, by] = p(x1, y1);
    return <rect key={key} x={Math.min(ax, bx)} y={Math.min(ay, by)} width={Math.abs(bx - ax)} height={Math.abs(by - ay)} {...line} />;
  };
  const [cx, cy] = p(60, 40);
  const [h1x, h1y] = p(60, 0);
  const [h2x, h2y] = p(60, 80);
  const [s1x, s1y] = p(12, 40);
  const [s2x, s2y] = p(108, 40);
  // penalty arcs: the part of a 10-yard circle around each spot outside the box
  const arc = (spot: number, box: number) => {
    const dx = Math.abs(box - spot);
    const dy = Math.sqrt(100 - dx * dx);
    const [ax, ay] = p(box, 40 - dy);
    const [bx, by] = p(box, 40 + dy);
    const sweep = (spot < 60) === (o === "horizontal") ? 1 : 0;
    return <path key={`arc${spot}`} d={`M ${ax} ${ay} A 10 10 0 0 ${sweep} ${bx} ${by}`} {...line} />;
  };
  return (
    <g>
      {rect(0, 0, 120, 80, "outline")}
      <line x1={h1x} y1={h1y} x2={h2x} y2={h2y} {...line} />
      <circle cx={cx} cy={cy} r={10} {...line} />
      <circle cx={cx} cy={cy} r={0.6} fill={colors.pitchLine} />
      {rect(0, 18, 18, 62, "box1")}
      {rect(102, 18, 120, 62, "box2")}
      {rect(0, 30, 6, 50, "six1")}
      {rect(114, 30, 120, 50, "six2")}
      {rect(-2, 36, 0, 44, "goal1")}
      {rect(120, 36, 122, 44, "goal2")}
      <circle cx={s1x} cy={s1y} r={0.6} fill={colors.pitchLine} />
      <circle cx={s2x} cy={s2y} r={0.6} fill={colors.pitchLine} />
      {arc(12, 18)}
      {arc(108, 102)}
    </g>
  );
}

export function Pitch({
  orientation = "horizontal",
  children,
  className,
  under,
}: {
  orientation?: Orientation;
  children?: React.ReactNode;
  className?: string;
  /** Layers drawn beneath the markings (heatmaps). */
  under?: React.ReactNode;
}) {
  const vb = orientation === "horizontal" ? "-3 -3 126 86" : "-3 -3 86 126";
  return (
    <svg viewBox={vb} className={className} role="img" aria-label="Football pitch">
      <rect x={orientation === "horizontal" ? -3 : -3} y={-3} width={orientation === "horizontal" ? 126 : 86}
            height={orientation === "horizontal" ? 86 : 126} fill={colors.pitch} rx={1.5} />
      {under}
      <Markings o={orientation} />
      {children}
    </svg>
  );
}
