import { NextResponse } from "next/server";

import { fplAuthed, readSession } from "@/lib/fpl-authed";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type PickBody = {
  chip?: string | null;
  picks?: {
    element: number;
    position: number;
    is_captain: boolean;
    is_vice_captain: boolean;
  }[];
};

export async function POST(request: Request) {
  const session = await readSession();
  if (!session) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }

  let body: PickBody;
  try {
    body = (await request.json()) as PickBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  if (!Array.isArray(body.picks) || body.picks.length !== 15) {
    return NextResponse.json({ error: "picks must be 15 players" }, { status: 400 });
  }

  const result = await fplAuthed(`my-team/${session.entryId}`, {
    method: "POST",
    body: JSON.stringify({
      chip: body.chip ?? null,
      picks: body.picks.map((p) => ({
        element: p.element,
        position: p.position,
        is_captain: Boolean(p.is_captain),
        is_vice_captain: Boolean(p.is_vice_captain),
      })),
    }),
  });
  if (!result.ok) {
    return NextResponse.json({ error: result.error }, { status: result.status });
  }
  return NextResponse.json(result.data ?? { ok: true });
}
