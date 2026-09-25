export const pct = (v: number | null | undefined, digits = 0) =>
  v == null || Number.isNaN(v) ? "–" : `${(v * 100).toFixed(digits)}%`;

export const num = (v: number | null | undefined, digits = 1) =>
  v == null || Number.isNaN(v) ? "–" : v.toFixed(digits);

export const int = (v: number | null | undefined) =>
  v == null || Number.isNaN(v) ? "–" : Math.round(v).toLocaleString("en-GB");

export const date = (iso: string, opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric" }) =>
  new Date(iso + "T12:00:00").toLocaleDateString("en-GB", opts);

export const seasonShort = (label: string) => `${label.slice(2, 4)}/${label.slice(7, 9)}`;

export const surname = (name: string) => {
  const parts = name.split(" ");
  return parts.length > 1 ? parts.slice(1).join(" ") : name;
};
