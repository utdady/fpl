"use client";

import clsx from "clsx";

import { useLiveContext } from "@/lib/live-context";

export function LiveToggle({
  on,
  onChange,
}: {
  on: boolean;
  onChange: (next: boolean) => void;
}) {
  const live = useLiveContext();
  const status = live?.status ?? "off";
  const at = live?.fetchedAt ?? null;

  const label =
    status === "loading"
      ? "connecting"
      : status === "error"
        ? "unavailable"
        : status === "ready" && at
          ? at.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
          : "off";

  return (
    <button
      type="button"
      onClick={() => onChange(!on)}
      title="Fetches in-play points through the server proxy, refreshed every 60 seconds"
      className={clsx(
        "flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[11px] transition-colors",
        on
          ? status === "error"
            ? "border-risk/50 text-risk"
            : "border-actual/50 text-actual"
          : "border-edge text-muted hover:border-edge-bright hover:text-ink",
      )}
    >
      <span
        className={clsx(
          "h-1.5 w-1.5 rounded-full",
          on && status === "ready" && "animate-pulse bg-actual",
          on && status === "loading" && "animate-pulse bg-muted",
          on && status === "error" && "bg-risk",
          !on && "bg-faint",
        )}
      />
      Live
      <span className="tnum text-faint">{label}</span>
    </button>
  );
}
