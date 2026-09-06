import type { BootstrapEvent } from "@/lib/fpl-account";

/** True when the event deadline is still in the future. */
export function deadlineUpcoming(
  deadline: string | null | undefined,
  now = Date.now(),
): boolean {
  if (!deadline) return false;
  const t = new Date(deadline).getTime();
  return Number.isFinite(t) && t > now;
}

/**
 * Next transfer deadline event. Trusts FPL `is_next` only while that
 * deadline is still ahead; otherwise picks the soonest future deadline.
 */
export function resolveNextEvent(
  events: BootstrapEvent[],
  now = Date.now(),
): BootstrapEvent | undefined {
  const flagged = events.find((e) => e.is_next);
  if (flagged && deadlineUpcoming(flagged.deadline_time, now)) return flagged;

  const upcoming = events
    .filter((e) => deadlineUpcoming(e.deadline_time, now))
    .sort(
      (a, b) =>
        new Date(a.deadline_time!).getTime() - new Date(b.deadline_time!).getTime(),
    );
  if (upcoming[0]) return upcoming[0];

  return (
    events.find((e) => e.is_current) ??
    events.find((e) => !e.finished) ??
    flagged
  );
}

/**
 * Active gameweek for Status / picks. Prefer entry.current_event while that
 * event is not finished; otherwise bootstrap `is_current`, then next deadline.
 */
export function resolveCurrentGw(
  entryCurrent: number | null | undefined,
  events: BootstrapEvent[],
): number {
  const fromBoot = events.find((e) => e.is_current)?.id;
  if (entryCurrent != null && entryCurrent > 0) {
    const row = events.find((e) => e.id === entryCurrent);
    if (row && !row.finished) return entryCurrent;
    if (fromBoot) return fromBoot;
    return resolveNextEvent(events)?.id ?? entryCurrent;
  }
  return fromBoot ?? resolveNextEvent(events)?.id ?? 1;
}
