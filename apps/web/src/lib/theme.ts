/** Colour roles for charts rendered in JS (SVG/Recharts). Mirrors globals.css. */
export const colors = {
  barca: "#e0457b",
  opponent: "#3987e5",
  third: "#c98500",
  win: "#0ca30c",
  draw: "#898781",
  loss: "#d03b3b",
  ink: "#eef0f4",
  ink2: "#c3c7d0",
  muted: "#9aa1ae",
  grid: "rgba(255,255,255,0.07)",
  axis: "rgba(255,255,255,0.18)",
  surface: "#151821",
  pitch: "#12161e",
  pitchLine: "rgba(255,255,255,0.16)",
} as const;

export const resultColor = (r: string) => (r === "W" ? colors.win : r === "D" ? colors.draw : colors.loss);

/** Single-hue sequential ramp (garnet) for densities, 0 → transparent, 1 → full. */
export const heat = (t: number) => {
  const a = Math.max(0, Math.min(1, t));
  return `rgba(224, 69, 123, ${(0.06 + 0.9 * Math.pow(a, 0.8)).toFixed(3)})`;
};

export const bandColor: Record<string, string> = {
  Low: "#5b6170",
  Moderate: "#3987e5",
  Elevated: "#c98500",
  High: "#e0457b",
};
