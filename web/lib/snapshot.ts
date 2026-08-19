import manifest from "@/public/data/manifest.json";

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/**
 * The day the FPL snapshot was captured, sliced straight out of the ISO string
 * rather than formatted through a locale, so the server and the client cannot
 * disagree and trigger a hydration mismatch.
 *
 * Any field that came from the snapshot rather than the frozen record needs this
 * beside it. Availability and news move daily; a bare percentage from a capture
 * several days old reads as current when it is not.
 */
export const SNAPSHOT_DAY: string | null = manifest.snapshot_as_of
  ? `${Number(manifest.snapshot_as_of.slice(8, 10))} ${
      MONTHS[Number(manifest.snapshot_as_of.slice(5, 7)) - 1]
    }`
  : null;
