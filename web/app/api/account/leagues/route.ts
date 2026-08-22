import { NextResponse } from "next/server";

import { fplAuthed, readSession } from "@/lib/fpl-authed";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type LeagueKind = "classic" | "h2h";

async function tryPaths(paths: string[], init: RequestInit) {
  let last: { status: number; error: string } = { status: 502, error: "FPL unreachable" };
  for (const path of paths) {
    const result = await fplAuthed(path, init);
    if (result.ok) return result;
    last = { status: result.status, error: result.error };
    if (result.status !== 404) return result;
  }
  return { ok: false as const, ...last };
}

export async function POST(request: Request) {
  const session = await readSession();
  if (!session) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }

  let body: {
    action?: string;
    kind?: LeagueKind;
    code?: string;
    name?: string;
    startEvent?: number;
    leagueId?: number;
  };
  try {
    body = (await request.json()) as typeof body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const kind: LeagueKind = body.kind === "h2h" ? "h2h" : "classic";
  const prefix = kind === "h2h" ? "leagues-h2h" : "leagues-classic";

  if (body.action === "join") {
    const code = typeof body.code === "string" ? body.code.trim() : "";
    if (!code) return NextResponse.json({ error: "League code required" }, { status: 400 });
    const result = await tryPaths(
      [`${prefix}/join-private`, `${prefix}/join`],
      { method: "POST", body: JSON.stringify({ code }) },
    );
    if (!result.ok) {
      return NextResponse.json({ error: result.error }, { status: result.status });
    }
    return NextResponse.json(result.data ?? { ok: true });
  }

  if (body.action === "create") {
    const name = typeof body.name === "string" ? body.name.trim() : "";
    if (!name) return NextResponse.json({ error: "League name required" }, { status: 400 });
    const startEvent =
      typeof body.startEvent === "number" && Number.isInteger(body.startEvent)
        ? body.startEvent
        : 1;
    const result = await fplAuthed(prefix, {
      method: "POST",
      body: JSON.stringify({ name, start_event: startEvent }),
    });
    if (!result.ok) {
      return NextResponse.json({ error: result.error }, { status: result.status });
    }
    return NextResponse.json(result.data ?? { ok: true });
  }

  if (body.action === "leave") {
    const leagueId = body.leagueId;
    if (!leagueId || !Number.isInteger(leagueId)) {
      return NextResponse.json({ error: "leagueId required" }, { status: 400 });
    }
    const result = await tryPaths(
      [`${prefix}/${leagueId}/leave`, `${prefix}/${leagueId}/leave-league`],
      { method: "POST", body: JSON.stringify({}) },
    );
    if (!result.ok) {
      return NextResponse.json({ error: result.error }, { status: result.status });
    }
    return NextResponse.json(result.data ?? { ok: true });
  }

  return NextResponse.json({ error: "Unknown action" }, { status: 400 });
}
