import { NextResponse } from "next/server";

import { loginWithPassword, loginWithRefreshToken, writeSession } from "@/lib/fpl-authed";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  let body: {
    email?: unknown;
    password?: unknown;
    sessionCookie?: unknown;
    refreshToken?: unknown;
  };
  try {
    body = (await request.json()) as typeof body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const tokenRaw =
    (typeof body.refreshToken === "string" ? body.refreshToken.trim() : "") ||
    (typeof body.sessionCookie === "string" ? body.sessionCookie.trim() : "");
  const email = typeof body.email === "string" ? body.email.trim() : "";
  const password = typeof body.password === "string" ? body.password : "";

  try {
    let session;
    if (tokenRaw) {
      session = await loginWithRefreshToken(tokenRaw);
    } else if (email && password) {
      session = await loginWithPassword(email, password);
    } else {
      return NextResponse.json(
        { error: "Paste your oidc.user value from fantasy.premierleague.com (see sign-in help)" },
        { status: 400 },
      );
    }
    await writeSession(session);
    return NextResponse.json({
      loggedIn: true,
      entryId: session.entryId,
      name: session.name,
      playerName: session.playerName,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Login failed";
    return NextResponse.json({ error: message }, { status: 401 });
  }
}
