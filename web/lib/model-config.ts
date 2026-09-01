import type { Manifest, ModelConfig, ModelRole } from "./types";

export function modelLabel(cfg: ModelConfig): string {
  const parts = [cfg.minutes_version, cfg.rates_version];
  const h = cfg.horizon ?? (cfg as { horizon_resolv?: number }).horizon_resolv;
  if (h != null) parts.push(`H=${h}`);
  if (cfg.strategy) parts.push(cfg.strategy);
  return parts.join(" · ");
}

export function roleTitle(role: ModelRole): string {
  switch (role) {
    case "frozen_record":
      return "Frozen record";
    case "live_resolv":
      return "Live re-solve";
    case "historical_control":
      return "V1 historical control";
    default:
      return "Model";
  }
}

export function roleDescription(role: ModelRole, manifest?: Manifest): string {
  const prod = manifest?.production;
  const control = manifest?.controls?.v1_gw1_baseline;
  switch (role) {
    case "frozen_record":
      return control
        ? `μ/σ from ${control.tag ?? "V1 control"} (${modelLabel(control)}). Captured before results; not updated when production defaults change.`
        : "μ/σ from the pre-deadline freeze. Not updated when production defaults change.";
    case "live_resolv":
      return prod
        ? `Re-projected from the cached FPL snapshot with current production defaults (${modelLabel(prod)}). Not a capture.py freeze.`
        : "Re-projected from the cached snapshot. Not a capture.py freeze.";
    case "historical_control":
      return "Scored-season V1 eleven and metrics from decision_decomp.csv / harness minutes=v1.";
    default:
      return "";
  }
}

/** Short chip for nav / section headers. */
export function modelChip(role: ModelRole, cfg?: ModelConfig): string {
  if (!cfg) return roleTitle(role);
  if (role === "frozen_record" && cfg.tag) return cfg.tag;
  return modelLabel(cfg);
}
