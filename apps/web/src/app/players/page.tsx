import type { Metadata } from "next";
import { PlayerList } from "@/components/player/player-list";

export const metadata: Metadata = { title: "Players" };

export default async function Page({ searchParams }: PageProps<"/players">) {
  const sp = await searchParams;
  return <PlayerList season={typeof sp.season === "string" ? sp.season : undefined} />;
}
