import { LeagueStandings } from "@/components/league-standings";

export default async function LeagueDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ kind?: string }>;
}) {
  const { id: raw } = await params;
  const { kind: kindRaw } = await searchParams;
  const id = Number(raw);
  const kind = kindRaw === "h2h" ? "h2h" : "classic";

  if (!Number.isInteger(id) || id <= 0) {
    return <p className="text-[13px] text-risk">Invalid league ID.</p>;
  }

  return <LeagueStandings leagueId={id} kind={kind} />;
}
