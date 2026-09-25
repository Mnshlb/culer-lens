import { Dashboard } from "@/components/overview/dashboard";

export default async function Page({ searchParams }: PageProps<"/">) {
  const sp = await searchParams;
  const asOf = typeof sp.as_of === "string" ? sp.as_of : undefined;
  const season = typeof sp.season === "string" ? sp.season : undefined;
  return <Dashboard asOf={asOf} season={season} />;
}
