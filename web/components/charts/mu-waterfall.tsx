"use client";

import { dec } from "@/lib/format";

const LABELS: Record<string, string> = {
  appearance: "App",
  goals: "G",
  assists: "A",
  clean_sheet: "CS",
  defensive: "DC",
  saves: "Sv",
  goals_conceded: "GC",
  yellow: "YC",
  bonus: "BPS",
};

const ORDER = [
  "appearance",
  "goals",
  "assists",
  "clean_sheet",
  "defensive",
  "saves",
  "goals_conceded",
  "yellow",
  "bonus",
];

export function MuWaterfall({ components }: { components: Record<string, number> }) {
  const rows = ORDER.map((k) => ({ key: k, value: components[k] ?? 0 })).filter(
    (r) => Math.abs(r.value) > 0.005,
  );
  const total = rows.reduce((s, r) => s + r.value, 0);
  const max = Math.max(0.5, ...rows.map((r) => Math.abs(r.value)));

  if (!rows.length) {
    return <p className="text-[11px] text-muted">No component breakdown.</p>;
  }

  return (
    <div className="space-y-1.5">
      {rows.map((r) => (
        <div key={r.key} className="flex items-center gap-2 text-[11px]">
          <span className="w-8 shrink-0 text-faint">{LABELS[r.key] ?? r.key}</span>
          <div className="relative h-3 flex-1 rounded bg-raised/60">
            <div
              className="absolute top-0 left-0 h-full rounded bg-model/70"
              style={{ width: `${(Math.abs(r.value) / max) * 100}%` }}
            />
          </div>
          <span className="tnum w-10 shrink-0 text-right text-model">{dec(r.value, 2)}</span>
        </div>
      ))}
      <div className="tnum border-t border-edge/50 pt-1.5 text-[11px] text-muted">
        Sum {dec(total, 2)} (sim means; may differ slightly from μ)
      </div>
    </div>
  );
}
