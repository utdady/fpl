import type { Manifest } from "@/lib/types";

const day = (iso: string | null) => (iso ? iso.slice(0, 10) : "unknown");

/**
 * Every page states which engine build produced the numbers above it. The whole
 * project rests on freeze discipline, so the tag travels into the UI.
 */
export function Provenance({ manifest }: { manifest: Manifest }) {
  const { engine, generated_at, snapshot_as_of } = manifest;

  return (
    <footer className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-edge py-5 font-mono text-[11px] text-faint">
      <span className="text-muted">V1.0</span>
      {engine.tag && <span>{engine.tag}</span>}
      {engine.sha && <span>{engine.sha}</span>}
      <span>exported {day(generated_at)}</span>
      <span>snapshot {day(snapshot_as_of)}</span>
      <span className="ml-auto max-w-md text-right leading-relaxed">
        Read-only viewer over frozen records. Not a recommendation product.
      </span>
    </footer>
  );
}
