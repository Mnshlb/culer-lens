"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/matches", label: "Match Centre" },
  { href: "/players", label: "Players" },
  { href: "/model", label: "Model Intelligence" },
  { href: "/about", label: "Methodology" },
];

function Wordmark() {
  return (
    <Link href="/" className="group flex items-center gap-2.5">
      <span aria-hidden className="grid h-7 w-7 place-items-center overflow-hidden rounded-md">
        <span className="flex h-full w-full">
          <span className="w-1/2 bg-[#a50044]" />
          <span className="w-1/2 bg-[#004d98]" />
        </span>
      </span>
      <span className="text-[15px] font-semibold tracking-tight">
        Culer <span className="text-muted-foreground font-medium">Lens</span>
      </span>
    </Link>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-border bg-background/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center gap-8 px-4 md:px-6">
          <Wordmark />
          <nav className="-mx-2 flex flex-1 gap-1 overflow-x-auto text-sm">
            {NAV.map((item) => {
              const active = item.href === "/" ? path === "/" : path.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "whitespace-nowrap rounded-md px-3 py-1.5 transition-colors",
                    active ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 md:px-6 md:py-8">{children}</main>
      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-[1400px] flex-col gap-4 px-4 py-6 text-xs text-muted-foreground md:flex-row md:items-center md:justify-between md:px-6">
          <div className="space-y-1">
            <p className="text-foreground/80">
              A personal, non-commercial project built with StatsBomb open data. Not affiliated with, endorsed by or
              connected to FC Barcelona or StatsBomb.
            </p>
            <p>
              Event data: StatsBomb Open Data (La Liga 2004/05-2020/21). Results and odds: football-data.co.uk.
            </p>
          </div>
          <div className="flex items-center gap-2 self-start md:self-auto">
            <span>Data by</span>
            <a href="https://github.com/statsbomb/open-data" target="_blank" rel="noreferrer"
               aria-label="StatsBomb open data (data credit)"
               className="inline-flex items-center rounded-md bg-white px-2.5 py-1.5">
              <Image src="/statsbomb-logo.png" alt="StatsBomb" width={110} height={28} className="h-5 w-auto" />
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
