import { NextResponse } from "next/server";

import { fplAuthed, readSession } from "@/lib/fpl-authed";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type TransferBody = {
  event?: number;
  chip?: string | null;
  transfers?: {
    element_in: number;
    element_out: number;
    purchase_price: number;
    selling_price: number;
  }[];
};

export async function POST(request: Request) {
  const session = await readSession();
  if (!session) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }

  let body: TransferBody;
  try {
    body = (await request.json()) as TransferBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  if (!Array.isArray(body.transfers) || body.transfers.length === 0) {
    return NextResponse.json({ error: "No transfers to confirm" }, { status: 400 });
  }
  if (!body.event || !Number.isInteger(body.event)) {
    return NextResponse.json({ error: "event is required" }, { status: 400 });
  }

  const result = await fplAuthed("transfers", {
    method: "POST",
    body: JSON.stringify({
      confirmed: true,
      entry: session.entryId,
      event: body.event,
      chip: body.chip ?? null,
      transfers: body.transfers,
    }),
  });
  if (!result.ok) {
    return NextResponse.json({ error: result.error }, { status: result.status });
  }
  return NextResponse.json(result.data ?? { ok: true });
}
