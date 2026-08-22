import type { LiveStat } from "./use-live";

export type LiveDisplayTone = "pending" | "blank" | "live" | "scored";

export type LiveDisplay = {
  label: string;
  tone: LiveDisplayTone;
  minutes: number | null;
  points: number | null;
};

/**
 * How to render in-play points on a card.
 * "-" until the player's fixture is done or they have minutes; 0 only once
 * the gameweek slot has recorded a zero.
 */
export function liveDisplay(
  stat: LiveStat,
  fixtureFinished: boolean,
): LiveDisplay {
  if (!fixtureFinished && stat.minutes === 0) {
    return { label: "—", tone: "pending", minutes: null, points: null };
  }
  if (stat.points === 0) {
    return {
      label: "0",
      tone: fixtureFinished ? "blank" : "live",
      minutes: stat.minutes,
      points: 0,
    };
  }
  return {
    label: String(stat.points),
    tone: "scored",
    minutes: stat.minutes,
    points: stat.points,
  };
}

export function liveToneClass(tone: LiveDisplayTone): string {
  switch (tone) {
    case "pending":
      return "text-faint";
    case "blank":
      return "text-risk";
    case "live":
    case "scored":
      return "text-actual";
  }
}

export function liveBadgeClass(tone: LiveDisplayTone): string {
  switch (tone) {
    case "pending":
      return "bg-raised text-faint";
    case "blank":
      return "bg-risk/15 text-risk";
    case "live":
    case "scored":
      return "bg-actual/12 text-actual";
  }
}
