import { MatchCentre } from "@/components/match/match-centre";

export default async function Page({ params }: PageProps<"/matches/[id]">) {
  const { id } = await params;
  return <MatchCentre id={Number(id)} />;
}
