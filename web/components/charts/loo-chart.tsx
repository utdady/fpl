"use client";

import type { AuditLooRow } from "@/lib/types";
import { dec } from "@/lib/format";

export function LooChart({ rows }: { rows: AuditLooRow[] }) {
  const top = rows.filter((r) => r.delta != null).slice(0, 12);
  if (!top.length) return null;

  const max = Math.max(...top.map((r) => r.delta ?? 0), 0.5);
  const height = top.length * 22 + 8;

  return (
    <div className="space-y-1">
      {top.map((r) => (
        <div key={r.id} className="flex items-center gap-2 text-[11px]">
          <span className="w-28 truncate text-ink" title={r.name}>
            {r.name}
          </span>
          <div className="relative h-3 flex-1 rounded bg-raised/50">
            <div
              className="absolute top-0 left-0 h-full rounded bg-oracle/80"
              style={{ width: `${((r.delta ?? 0) / max) * 100}%` }}
            />
          </div>
          <span className="tnum w-10 text-right text-model">{dec(r.delta, 2)}</span>
          <span className="w-16 text-[10px] text-faint">{r.tag}</span>
        </div>
      ))}
      <svg width={0} height={height} className="sr-only" aria-hidden />
    </div>
  );
}
