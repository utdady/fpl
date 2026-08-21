import { NextResponse } from "next/server";

/**
 * Server-side proxy for the FPL API, which sends no Access-Control-Allow-Origin
 * header and so cannot be called from the browser.
 *
 * Only the read-only endpoints the UI needs are allowed through, and each has a
 * revalidate window so Vercel's data cache absorbs traffic. Without this a live
 * gameweek would hit the upstream API once per viewer per poll.
 */
const UPSTREAM = "https://fantasy.premierleague.com/api";

const ALLOWED: { pattern: RegExp; revalidate: number }[] = [
  // Prices, ownership and injury news. Changes at most a few times a day.
  { pattern: /^bootstrap-static$/, revalidate: 600 },
  { pattern: /^fixtures$/, revalidate: 600 },
  // In-play points. The only endpoint that needs to be near-live.
  { pattern: /^event\/\d{1,2}\/live$/, revalidate: 60 },
  // A manager's own squad.
  { pattern: /^entry\/\d+$/, revalidate: 300 },
  { pattern: /^entry\/\d+\/event\/\d{1,2}\/picks$/, revalidate: 300 },
  { pattern: /^entry\/\d+\/history$/, revalidate: 300 },
  { pattern: /^entry\/\d+\/transfers$/, revalidate: 300 },
  { pattern: /^element-summary\/\d+$/, revalidate: 600 },
];

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  const route = path.join("/");

  const rule = ALLOWED.find((entry) => entry.pattern.test(route));
  if (!rule) {
    return NextResponse.json(
      { error: "Endpoint not proxied", route },
      { status: 403 },
    );
  }

  try {
    const upstream = await fetch(`${UPSTREAM}/${route}/`, {
      headers: { "User-Agent": "fpl-model/1.0 (research viewer)" },
      next: { revalidate: rule.revalidate },
    });

    if (!upstream.ok) {
      return NextResponse.json(
        { error: "Upstream error", status: upstream.status },
        { status: upstream.status },
      );
    }

    return NextResponse.json(await upstream.json(), {
      headers: {
        "Cache-Control": `public, s-maxage=${rule.revalidate}, stale-while-revalidate=${
          rule.revalidate * 4
        }`,
      },
    });
  } catch {
    return NextResponse.json({ error: "Upstream unreachable" }, { status: 502 });
  }
}
