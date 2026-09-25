"use client";

export function ConfusionMatrix({ matrix, labels }: { matrix: number[][]; labels: string[] }) {
  const max = Math.max(...matrix.flat());
  return (
    <div className="inline-grid grid-cols-[auto_repeat(3,72px)] gap-1 text-xs">
      <div />
      {labels.map((l) => (
        <div key={l} className="pb-1 text-center text-muted-foreground">{l}</div>
      ))}
      {matrix.map((row, i) => (
        <div key={i} className="contents">
          <div className="flex items-center pr-2 text-muted-foreground">{labels[i]}</div>
          {row.map((v, j) => (
            <div key={j} className="grid h-14 place-items-center rounded-md font-semibold tabular"
                 style={{ background: `rgba(57,135,229,${0.08 + 0.75 * (v / max)})` }}>
              {v}
            </div>
          ))}
        </div>
      ))}
      <div />
      <div className="col-span-3 pt-1 text-center text-[11px] text-muted-foreground">rows = actual · columns = most likely prediction</div>
    </div>
  );
}
