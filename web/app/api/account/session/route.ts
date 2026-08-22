import { NextResponse } from "next/server";

import { readSession } from "@/lib/fpl-authed";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const session = await readSession();
  if (!session) {
    return NextResponse.json({
      loggedIn: false,
      entryId: null,
      name: null,
      playerName: null,
    });
  }
  return NextResponse.json({
    loggedIn: true,
    entryId: session.entryId,
    name: session.name,
    playerName: session.playerName,
  });
}
