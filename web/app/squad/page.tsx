import { redirect } from "next/navigation";

import { getLabSeasons } from "@/lib/data";

export default async function SquadIndex() {
  const latest = (await getLabSeasons()).at(-1);
  redirect(latest ? `/squad/${latest}/1` : "/");
}
