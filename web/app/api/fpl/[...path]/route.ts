import { NextResponse } from "next/server";

/**
 * Server-side proxy for the FPL API, which sends no Access-Control-Allow-Origin
 * header and so cannot be called from the browser.
 *
 * Calendar / entry state (bootstrap, entry) is never cached — My team and
 * deadlines must track live FPL. Short revalidate windows remain only for
 * high-churn or high-traffic reads (live points, fixtures, leagues).
 */
const UPSTREAM = "https://fantasy.premierleague.com/api";

/** revalidate: 0 → fetch with cache: "no-store" and Cache-Control: no-store */
const ALLOWED: { pattern: RegExp; revalidate: number }[] = [
  // Current / next GW flags and deadlines — must stay live.
  { pattern: /^bootstrap-static$/, revalidate: 0 },
  { pattern: /^fixtures$/, revalidate: 60 },
  { pattern: /^event\/\d{1,2}\/live$/, revalidate: 60 },
  // Manager entry state — current_event, points, history.
  { pattern: /^entry\/\d+$/, revalidate: 0 },
  { pattern: /^entry\/\d+\/event\/\d{1,2}\/picks$/, revalidate: 0 },
  { pattern: /^entry\/\d+\/history$/, revalidate: 0 },
  { pattern: /^entry\/\d+\/transfers$/, revalidate: 0 },
  { pattern: /^element-summary\/\d+$/, revalidate: 300 },
  { pattern: /^leagues-classic\/\d+\/standings$/, revalidate: 120 },
  { pattern: /^leagues-h2h\/\d+\/standings$/, revalidate: 120 },
  { pattern: /^dream-team\/\d{1,2}$/, revalidate: 120 },
];

export async function GET(
  request: Request,
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
    const qs = new URL(request.url).search;
    const live = rule.revalidate === 0;
    const upstream = await fetch(`${UPSTREAM}/${route}/${qs}`, {
      headers: { "User-Agent": "fpl-model/1.0 (research viewer)" },
      ...(live
        ? { cache: "no-store" as const }
        : { next: { revalidate: rule.revalidate } }),
    });

    if (!upstream.ok) {
      return NextResponse.json(
        { error: "Upstream error", status: upstream.status },
        { status: upstream.status },
      );
    }

    return NextResponse.json(await upstream.json(), {
      headers: {
        "Cache-Control": live
          ? "no-store, must-revalidate"
          : `public, s-maxage=${rule.revalidate}, stale-while-revalidate=${
              rule.revalidate * 4
            }`,
      },
    });
  } catch {
    return NextResponse.json({ error: "Upstream unreachable" }, { status: 502 });
  }
}
