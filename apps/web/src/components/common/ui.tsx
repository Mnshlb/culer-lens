"use client";

import { AlertTriangle, Info } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { API_URL, type ApiError } from "@/lib/api";
import { resultColor } from "@/lib/theme";
import { cn } from "@/lib/utils";

export function Panel({
  title,
  subtitle,
  action,
  children,
  className,
  bodyClassName,
}: {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <Card className={cn("gap-0 overflow-hidden border-border bg-card p-0 shadow-none", className)}>
      {(title || action) && (
        <div className="flex items-start justify-between gap-4 px-5 pt-4">
          <div>
            {title && <h2 className="text-[13px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">{title}</h2>}
            {subtitle && <p className="mt-1 text-sm text-muted-foreground/80">{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      <div className={cn("p-5", bodyClassName)}>{children}</div>
    </Card>
  );
}

export function PageTitle({ eyebrow, title, children }: { eyebrow?: string; title: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 md:mb-8 md:flex-row md:items-end md:justify-between">
      <div>
        {eyebrow && <p className="mb-1 text-xs font-medium uppercase tracking-[0.14em] text-primary">{eyebrow}</p>}
        <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">{title}</h1>
        <div className="rule-blaugrana mt-3 w-40" />
      </div>
      {children}
    </div>
  );
}

export function Stat({ label, value, sub, className }: { label: string; value: React.ReactNode; sub?: React.ReactNode; className?: string }) {
  return (
    <div className={cn("min-w-0", className)}>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

export function ResultChip({ result, size = "md", title }: { result: string; size?: "sm" | "md"; title?: string }) {
  return (
    <span
      title={title}
      className={cn(
        "inline-grid place-items-center rounded-md font-semibold text-white",
        size === "sm" ? "h-5 w-5 text-[10px]" : "h-7 w-7 text-xs",
      )}
      style={{ background: resultColor(result) }}
    >
      {result}
    </span>
  );
}

export function InfoTip({ children }: { children: React.ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button type="button" aria-label="More information" className="text-muted-foreground hover:text-foreground">
          <Info className="h-3.5 w-3.5" />
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs text-xs leading-relaxed">{children}</TooltipContent>
    </Tooltip>
  );
}

export function Loading({ className }: { className?: string }) {
  return <Skeleton className={cn("h-40 w-full rounded-xl bg-muted", className)} />;
}

export function ErrorState({ error }: { error: ApiError | Error | null }) {
  const status = error && "status" in error ? error.status : undefined;
  return (
    <div className="flex items-start gap-3 rounded-xl border border-border bg-card p-5 text-sm">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[#c98500]" />
      <div className="space-y-1">
        <p className="font-medium">{status === 404 ? "Not available" : "Could not load data"}</p>
        <p className="text-muted-foreground">
          {error?.message}
          {!status && (
            <>
              {" "}Is the API running at <code className="text-foreground">{API_URL}</code>? Start it with{" "}
              <code className="text-foreground">make api</code>.
            </>
          )}
        </p>
      </div>
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">{children}</p>;
}
