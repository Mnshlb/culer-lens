import { PlayerProfile } from "@/components/player/player-profile";

export default async function Page({ params }: PageProps<"/players/[id]">) {
  const { id } = await params;
  return <PlayerProfile id={Number(id)} />;
}
