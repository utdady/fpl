/** HttpOnly cookie for PingOne OIDC session. Never exposed to JS. */

export const SESSION_COOKIE = "fpl_session";

export type FplSession = {
  refreshToken?: string;
  accessToken?: string;
  accessTokenExpiresAt?: number;
  entryId: number;
  name: string;
  playerName: string;
};

export type ParsedOidcPaste = {
  refreshToken?: string;
  accessToken?: string;
  /** Unix seconds, from oidc-client expires_at */
  expiresAtSec?: number;
};

export function encodeSession(session: FplSession): string {
  return encodeURIComponent(JSON.stringify(session));
}

export function decodeSession(raw: string | undefined): FplSession | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(decodeURIComponent(raw)) as Partial<FplSession> & {
      cookies?: Record<string, string>;
    };

    // Legacy cookie sessions from the first manager cut — force re-login.
    if (parsed.cookies) return null;

    const hasRefresh = typeof parsed.refreshToken === "string" && parsed.refreshToken.length > 0;
    const hasAccess = typeof parsed.accessToken === "string" && parsed.accessToken.length > 0;
    if (
      !parsed ||
      (!hasRefresh && !hasAccess) ||
      typeof parsed.entryId !== "number" ||
      !Number.isInteger(parsed.entryId) ||
      parsed.entryId <= 0
    ) {
      return null;
    }
    return {
      refreshToken: hasRefresh ? parsed.refreshToken : undefined,
      accessToken: hasAccess ? parsed.accessToken : undefined,
      accessTokenExpiresAt:
        typeof parsed.accessTokenExpiresAt === "number" ? parsed.accessTokenExpiresAt : undefined,
      entryId: parsed.entryId,
      name: typeof parsed.name === "string" ? parsed.name : "",
      playerName: typeof parsed.playerName === "string" ? parsed.playerName : "",
    };
  } catch {
    return null;
  }
}

export function sessionCookieOptions(maxAge = 60 * 60 * 24 * 14) {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge,
  };
}

function looksLikeJwt(value: string): boolean {
  const parts = value.split(".");
  return parts.length === 3 && parts.every((p) => p.length > 0);
}

function stripWrappingQuotes(raw: string): string {
  let s = raw.trim();
  // Smart quotes / plain quotes around the whole paste
  if (
    (s.startsWith('"') && s.endsWith('"')) ||
    (s.startsWith("'") && s.endsWith("'")) ||
    (s.startsWith("\u201c") && s.endsWith("\u201d"))
  ) {
    s = s.slice(1, -1);
  }
  // Chrome sometimes leaves escaped quotes when copying
  s = s.replace(/\\"/g, '"');
  return s.trim();
}

function tryParseJson(raw: string): unknown | null {
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/**
 * Accepts:
 * - full oidc.user JSON (preferred)
 * - bare refresh_token
 * - bare access_token JWT (short-lived only)
 */
export function parseOidcPaste(pasted: string): ParsedOidcPaste {
  const trimmed = stripWrappingQuotes(pasted);
  if (!trimmed) throw new Error("Paste is empty");

  if (trimmed.startsWith("oidc.user:")) {
    throw new Error(
      "That looks like the Local Storage key name. Paste the VALUE cell next to oidc.user:…, not the key.",
    );
  }

  let json = tryParseJson(trimmed);
  // Double-encoded string: "\"{...}\""
  if (typeof json === "string") {
    json = tryParseJson(json) ?? json;
  }

  if (json && typeof json === "object" && !Array.isArray(json)) {
    const obj = json as Record<string, unknown>;
    const refresh =
      typeof obj.refresh_token === "string" ? obj.refresh_token.trim() : undefined;
    const access =
      typeof obj.access_token === "string" ? obj.access_token.trim() : undefined;
    const expiresAtSec =
      typeof obj.expires_at === "number"
        ? obj.expires_at
        : typeof obj.expires_at === "string" && Number.isFinite(Number(obj.expires_at))
          ? Number(obj.expires_at)
          : undefined;

    if (!refresh && !access) {
      throw new Error(
        "JSON pasted, but it has no refresh_token or access_token. Copy the full oidc.user value from Local Storage.",
      );
    }
    return { refreshToken: refresh, accessToken: access, expiresAtSec };
  }

  // Bare token
  if (looksLikeJwt(trimmed)) {
    // Access/id tokens are JWTs; PingOne refresh tokens often are too.
    // Prefer treating bare JWT as access token if payload has exp and no "rti".
    try {
      const mid = trimmed.split(".")[1]!.replace(/-/g, "+").replace(/_/g, "/");
      const json = globalThis.Buffer
        ? globalThis.Buffer.from(mid, "base64").toString("utf8")
        : atob(mid);
      const payload = JSON.parse(json) as { exp?: number; token_use?: string };
      if (payload.token_use === "access" || (payload.exp && !("rti" in (payload as object)))) {
        return { accessToken: trimmed, expiresAtSec: payload.exp };
      }
    } catch {
      /* fall through — treat as refresh */
    }
    return { refreshToken: trimmed };
  }

  // Opaque refresh token
  if (trimmed.length < 20) {
    throw new Error("Paste looks too short. Copy the full oidc.user JSON value or refresh_token.");
  }
  return { refreshToken: trimmed };
}

/** @deprecated use parseOidcPaste */
export function parseRefreshToken(pasted: string): string {
  const parsed = parseOidcPaste(pasted);
  if (parsed.refreshToken) return parsed.refreshToken;
  throw new Error("No refresh_token in paste. Paste the full oidc.user JSON instead.");
}
