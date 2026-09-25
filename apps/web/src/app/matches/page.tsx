import type { Metadata } from "next";
import { FixtureList } from "@/components/matches/fixture-list";

export const metadata: Metadata = { title: "Match Centre" };

export default async function Page({ searchParams }: PageProps<"/matches">) {
  const sp = await searchParams;
  return <FixtureList season={typeof sp.season === "string" ? sp.season : undefined} />;
}
