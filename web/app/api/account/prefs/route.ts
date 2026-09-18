import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

import { NextResponse } from "next/server";

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

function runPrefs(
  root: string,
  prefsJson: string,
): Promise<{ ok: true; data: unknown } | { ok: false; error: string }> {
  return new Promise((resolve) => {
    const args = ["fpl.py", "prefs", "--json", "--prefs", "-"];
    const child = spawn(pythonBin(root), args, {
      cwd: root,
      windowsHide: true,
    });
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill();
      resolve({ ok: false, error: "Preference solver timed out" });
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
        error: `Preference solver unavailable — run locally (${err.message})`,
      });
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      if (code !== 0) {
        const tail = stderr.trim().slice(-240);
        resolve({
          ok: false,
          error: tail
            ? `Preference solver failed: ${tail}`
            : "Preference solver unavailable — run locally",
        });
        return;
      }
      try {
        resolve({ ok: true, data: lastJsonObject(stdout) });
      } catch {
        resolve({ ok: false, error: "Preference solver returned non-JSON" });
      }
    });
    child.stdin.write(prefsJson);
    child.stdin.end();
  });
}

export async function POST(request: Request) {
  const root = repoRoot();
  if (!fs.existsSync(path.join(root, "fpl.py"))) {
    return NextResponse.json(
      { error: "Preference solver unavailable — run locally" },
      { status: 503 },
    );
  }
  let body: unknown = {};
  try {
    body = await request.json();
  } catch {
    body = {};
  }
  if (body == null || typeof body !== "object") {
    return NextResponse.json({ error: "prefs body must be an object" }, { status: 400 });
  }
  const result = await runPrefs(root, JSON.stringify(body));
  if (!result.ok) {
    const status = result.error.includes("must be") ? 400 : 503;
    return NextResponse.json({ error: result.error }, { status });
  }
  return NextResponse.json(result.data);
}

export async function GET() {
  return NextResponse.json({
    bank_menu_m: [0, 0.5, 1, 1.5, 2],
    club_max_allowed: [0, 1, 2],
    primitives: ["lock", "ban", "min_bank_m", "club_max"],
    copy: "Best squad given your constraints (same Model A objective).",
  });
}
