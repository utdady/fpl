import { redirect } from "next/navigation";

import { getLabSeasons } from "@/lib/data";

export default async function LabIndex() {
  const latest = (await getLabSeasons()).at(-1);
  redirect(latest ? `/lab/${latest}` : "/");
}
