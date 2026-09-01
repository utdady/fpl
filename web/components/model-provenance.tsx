import clsx from "clsx";

import { modelChip, roleDescription, roleTitle } from "@/lib/model-config";
import type { Manifest, ModelConfig, ModelRole } from "@/lib/types";

/**
 * Compact banner: which model produced the numbers on this page.
 * Keeps V1 control visible even when production runs v2am_s.
 */
export function ModelProvenance({
  role,
  config,
  manifest,
  className,
  compact = false,
}: {
  role: ModelRole;
  config?: ModelConfig;
  manifest?: Manifest;
  className?: string;
  compact?: boolean;
}) {
  const chip = modelChip(role, config ?? manifest?.production);
  const desc = roleDescription(role, manifest);

  if (compact) {
    return (
      <p className={clsx("font-mono text-[10.5px] text-faint", className)}>
        <span className="text-muted">{roleTitle(role)}</span>
        {" · "}
        <span className="text-model">{chip}</span>
      </p>
    );
  }

  return (
    <div
      className={clsx(
        "rounded-md border border-edge bg-raised/30 px-3 py-2 text-[11px] leading-relaxed",
        className,
      )}
    >
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span className="font-medium text-ink">{roleTitle(role)}</span>
        <span className="rounded bg-model/10 px-1.5 py-px font-mono text-[10px] text-model">
          {chip}
        </span>
        {manifest?.production && role === "live_resolv" && manifest.engine.tag && (
          <span className="font-mono text-[10px] text-faint">{manifest.engine.tag}</span>
        )}
      </div>
      <p className="mt-1 text-muted">{desc}</p>
    </div>
  );
}
