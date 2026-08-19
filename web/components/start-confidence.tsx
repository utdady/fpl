"use client";

import { calibratedStart, pct } from "@/lib/format";
import { SNAPSHOT_DAY } from "@/lib/snapshot";

/**
 * Three opinions on whether this player starts, side by side:
 *   model       V1 p_start
 *   FPL         chance_of_playing_next_round, live season only
 *   historical  actual start rate observed at this confidence (E013)
 *
 * The third row is the point. E013 found p_start >= 0.90 delivers a 75-78%
 * start rate across four seasons, so a high model number must never be shown
 * on its own.
 */
export function StartConfidence({
  model,
  fpl,
  p60,
}: {
  model: number | null | undefined;
  fpl: number | null | undefined;
  p60: number | null | undefined;
}) {
  const observed = calibratedStart(model);
  const overconfident = model != null && observed != null && model - observed > 0.08;

  const rows = [
    { label: "V1 model", value: model, color: "var(--color-model)" },
    fpl != null
      ? { label: "FPL availability", value: fpl / 100, color: "var(--color-ink)" }
      : null,
    { label: "Historical at this confidence", value: observed, color: "var(--color-risk)" },
    p60 != null ? { label: "P(60+ minutes)", value: p60, color: "var(--color-muted)" } : null,
  ].filter(Boolean) as { label: string; value: number | null; color: string }[];

  return (
    <div>
      <div className="label-xs mb-2">Will they start?</div>
      <div className="space-y-2">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center gap-3">
            <span className="w-[168px] shrink-0 text-[11px] text-muted">{row.label}</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-raised">
              <div
                className="h-full rounded-full transition-[width] duration-500"
                style={{
                  width: `${Math.round((row.value ?? 0) * 100)}%`,
                  background: row.color,
                }}
              />
            </div>
            <span className="tnum w-10 shrink-0 text-right text-[11.5px] font-medium">
              {pct(row.value, 0)}
            </span>
          </div>
        ))}
      </div>

      {fpl !== undefined && SNAPSHOT_DAY && (
        <p className="mt-2 text-[10px] leading-relaxed text-faint">
          {fpl === null
            ? `No FPL doubt was recorded at the ${SNAPSHOT_DAY} snapshot. That is not the same as none now.`
            : `FPL availability is from the ${SNAPSHOT_DAY} snapshot, not live.`}{" "}
          Check the official site before a deadline.
        </p>
      )}

      {overconfident && (
        <p className="mt-2.5 border-l-2 border-risk/40 pl-2.5 text-[10.5px] leading-relaxed text-muted">
          The model is {pct((model ?? 0) - (observed ?? 0), 0)} more confident than the
          four-season evidence supports at this level. Upper-tail playing-time
          overconfidence is V1&apos;s known repeatable weakness (E013) and the target of
          V2A-M.
        </p>
      )}
    </div>
  );
}
