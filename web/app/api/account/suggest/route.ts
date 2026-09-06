import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

import { NextResponse } from "next/server";

import { fplAuthed, readSession } from "@/lib/fpl-authed";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 180;

const TIMEOUT_MS = 180_000;

function repoRoot(): string {
  if (process.env.FPL_ROOT) return process.env.FPL_ROOT;
  const cwd = process.cwd();
  if (fs.existsSync(path.join(cwd, "fpl.py"))) return cwd;
  const parent = path.resolve(cwd, "..");
  if (fs.existsSync(path.join(parent, "fpl.py"))) return parent;
  return parent;
}

function pythonBin(root: string): string {
  if (process.env.FPL_PYTHON) return process.env.FPL_PYTHON;
  const win = path.join(root, ".venv", "Scripts", "python.exe");
  const unix = path.join(root, ".venv", "bin", "python");
  if (fs.existsSync(win)) return win;
  if (fs.existsSync(unix)) return unix;
  return "python";
}

function lastJsonObject(text: string): unknown {
  const lines = text.trim().split(/\r?\n/);
  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i]?.trim();
    if (line?.startsWith("{")) return JSON.parse(line);
  }
  return JSON.parse(text.trim());
}

function runSuggest(
  root: string,
  squadJson: string,
  allowHit: boolean,
): Promise<{ ok: true; data: unknown } | { ok: false; error: string }> {
  return new Promise((resolve) => {
    const args = ["fpl.py", "suggest", "--squad", "-", "--json"];
    if (allowHit) args.push("--allow-hit");
    const child = spawn(pythonBin(root), args, {
      cwd: root,
      windowsHide: true,
    });
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill();
      resolve({ ok: false, error: "Suggestor timed out" });
    }, TIMEOUT_MS);
    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString();
    });
    child.on("error", (err) => {
      clearTimeout(timer);
      resolve({
        ok: false,
        error: `Python suggestor unavailable — run locally (${err.message})`,
      });
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      if (code !== 0) {
        const tail = stderr.trim().slice(-240);
        resolve({
          ok: false,
          error: tail
            ? `Python suggestor unavailable — run locally: ${tail}`
            : "Python suggestor unavailable — run locally",
        });
        return;
      }
      try {
        resolve({ ok: true, data: lastJsonObject(stdout) });
      } catch {
        resolve({ ok: false, error: "Suggestor returned non-JSON" });
      }
    });
    child.stdin.write(squadJson);
    child.stdin.end();
  });
}

export async function GET(request: Request) {
  const session = await readSession();
  if (!session) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }
  const team = await fplAuthed(`my-team/${session.entryId}`);
  if (!team.ok) {
    return NextResponse.json({ error: team.error }, { status: team.status });
  }

  const url = new URL(request.url);
  const allowHit = url.searchParams.get("allow_hit") !== "0";
  const root = repoRoot();
  if (!fs.existsSync(path.join(root, "fpl.py"))) {
    return NextResponse.json(
      { error: "Python suggestor unavailable — run locally" },
      { status: 503 },
    );
  }

  const result = await runSuggest(root, JSON.stringify(team.data), allowHit);
  if (!result.ok) {
    return NextResponse.json({ error: result.error }, { status: 503 });
  }
  return NextResponse.json(result.data);
}

export async function POST(request: Request) {
  return GET(request);
}
