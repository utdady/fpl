import { redirect } from "next/navigation";

export default async function LeagueDetailRedirect({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ kind?: string }>;
}) {
  const { id } = await params;
  const { kind } = await searchParams;
  const qs = kind ? `?kind=${kind}` : "";
  redirect(`/me/leagues/${id}${qs}`);
}
