import { cookies } from "next/headers";

import {
  decodeSession,
  encodeSession,
  parseOidcPaste,
  SESSION_COOKIE,
  sessionCookieOptions,
  type FplSession,
  type ParsedOidcPaste,
} from "./fpl-session";

const FPL = "https://fantasy.premierleague.com/api";
const OIDC_TOKEN_URL = "https://account.premierleague.com/as/token";
const OIDC_CLIENT_ID = "bfcbaf69-aade-4c1b-8f00-c1cb8a193030";
const UA = "fpl-model/1.0 (research viewer)";

type TokenResponse = {
  access_token?: string;
  refresh_token?: string;
  expires_in?: number;
  error?: string;
  error_description?: string;
};

type MeResponse = {
  player?: { entry?: number; first_name?: string; last_name?: string };
};

type EntryResponse = { name?: string };

export async function readSession(): Promise<FplSession | null> {
  const store = await cookies();
  return decodeSession(store.get(SESSION_COOKIE)?.value);
}

export async function writeSession(session: FplSession) {
  // Keep the cookie small: once we have a working refresh token, drop the
  // bulky access token (it can be re-fetched).
  const toStore: FplSession =
    session.refreshToken && session.accessToken && session.accessToken.length > 800
      ? {
          refreshToken: session.refreshToken,
          accessTokenExpiresAt: session.accessTokenExpiresAt,
          entryId: session.entryId,
          name: session.name,
          playerName: session.playerName,
        }
      : session;

  const encoded = encodeSession(toStore);
  if (encoded.length > 3900) {
    if (session.refreshToken) {
      const slim = encodeSession({
        refreshToken: session.refreshToken,
        entryId: session.entryId,
        name: session.name,
        playerName: session.playerName,
      });
      if (slim.length <= 3900) {
        const store = await cookies();
        store.set(SESSION_COOKIE, slim, sessionCookieOptions());
        return;
      }
    }
    // Access-only session — store a truncated marker is useless; keep access.
    if (session.accessToken) {
      const slim = encodeSession({
        accessToken: session.accessToken,
        accessTokenExpiresAt: session.accessTokenExpiresAt,
        entryId: session.entryId,
        name: session.name,
        playerName: session.playerName,
      });
      if (slim.length <= 3900) {
        const store = await cookies();
        store.set(SESSION_COOKIE, slim, sessionCookieOptions());
        return;
      }
    }
    throw new Error("FPL session is too large to store in a cookie");
  }
  const store = await cookies();
  store.set(SESSION_COOKIE, encoded, sessionCookieOptions());
}

export async function clearSession() {
  const store = await cookies();
  store.set(SESSION_COOKIE, "", sessionCookieOptions(0));
}

async function exchangeRefreshToken(refreshToken: string): Promise<{
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
}> {
  let res: Response;
  try {
    res = await fetch(OIDC_TOKEN_URL, {
      method: "POST",
      headers: {
        "User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded",
        Accept: "application/json",
      },
      body: new URLSearchParams({
        grant_type: "refresh_token",
        refresh_token: refreshToken,
        client_id: OIDC_CLIENT_ID,
      }),
      cache: "no-store",
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "network error";
    throw new Error(`Could not reach FPL sign-in (${msg})`);
  }

  const payload = (await res.json()) as TokenResponse;
  if (!res.ok || !payload.access_token) {
    if (payload.error === "invalid_grant") throw new Error("invalid_grant");
    const detail = [payload.error, payload.error_description].filter(Boolean).join(": ");
    throw new Error(detail || `FPL token exchange failed (${res.status})`);
  }

  return {
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token ?? refreshToken,
    expiresAt: Date.now() + (payload.expires_in ?? 300) * 1000 - 15_000,
  };
}

async function loadIdentity(accessToken: string): Promise<{
  entryId: number;
  name: string;
  playerName: string;
}> {
  let res: Response;
  try {
    res = await fetch(`${FPL}/me/`, {
      headers: {
        "User-Agent": UA,
        Accept: "application/json",
        "X-API-Authorization": `Bearer ${accessToken}`,
      },
      cache: "no-store",
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "network error";
    throw new Error(`Could not verify FPL session (${msg})`);
  }

  if (res.status === 401 || res.status === 403) {
    throw new Error("FPL did not accept this access token — paste a fresher oidc.user JSON");
  }
  if (!res.ok) {
    throw new Error(`FPL /me failed (${res.status})`);
  }

  const me = (await res.json()) as MeResponse;
  const entryId = me.player?.entry;
  if (!entryId) throw new Error("This FPL account has no team");

  let name = `Entry ${entryId}`;
  try {
    const entryRes = await fetch(`${FPL}/entry/${entryId}/`, {
      headers: { "User-Agent": UA, Accept: "application/json" },
      next: { revalidate: 300 },
    });
    if (entryRes.ok) {
      const entry = (await entryRes.json()) as EntryResponse;
      if (entry.name) name = entry.name;
    }
  } catch {
    /* public entry lookup is best-effort */
  }

  const playerName = [me.player?.first_name, me.player?.last_name]
    .filter(Boolean)
    .join(" ");

  return { entryId, name, playerName };
}

function accessExpiryMs(paste: ParsedOidcPaste): number | undefined {
  if (paste.expiresAtSec == null) return undefined;
  // oidc-client uses unix seconds; tolerate accidental milliseconds.
  const sec = paste.expiresAtSec > 1e12 ? paste.expiresAtSec / 1000 : paste.expiresAtSec;
  return sec * 1000;
}

function accessStillValid(paste: ParsedOidcPaste): boolean {
  if (!paste.accessToken) return false;
  const exp = accessExpiryMs(paste);
  if (exp == null) return true;
  return exp > Date.now() + 10_000;
}

/**
 * Login strategy:
 * 1. If the paste has a live access_token, use it immediately (reliable).
 * 2. Optionally exchange refresh_token for a longer session.
 * 3. If only a dead refresh_token was pasted, tell the user to paste full JSON.
 */
export async function loginWithRefreshToken(raw: string): Promise<FplSession> {
  const paste = parseOidcPaste(raw);

  let accessToken: string | undefined;
  let refreshToken: string | undefined;
  let expiresAt: number | undefined;

  // 1) Prefer a still-valid access token from the paste — FPL's site often
  // rotates refresh tokens before you finish pasting.
  if (accessStillValid(paste)) {
    accessToken = paste.accessToken;
    expiresAt = accessExpiryMs(paste) ?? Date.now() + 4 * 60_000;
  }

  // 2) Try to exchange refresh for a durable session (and fresher access).
  if (paste.refreshToken) {
    try {
      const tokens = await exchangeRefreshToken(paste.refreshToken);
      accessToken = tokens.accessToken;
      refreshToken = tokens.refreshToken;
      expiresAt = tokens.expiresAt;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "refresh failed";
      if (!accessToken) {
        if (msg === "invalid_grant") {
          throw new Error(
            paste.accessToken
              ? "Your access token in that paste has expired and the refresh token was already rotated. On FPL: hard-refresh the page (Ctrl+Shift+R), run the Console copy snippet again, and paste here within 5 seconds."
              : "You pasted a refresh token that FPL has already rotated. Paste the FULL oidc.user JSON (must start with { and include access_token), not only the refresh_token string.",
          );
        }
        throw new Error(msg);
      }
      // Keep access-token session; drop dead refresh.
      refreshToken = undefined;
    }
  }

  if (!accessToken) {
    throw new Error(
      "No usable token. Paste the full oidc.user JSON from the Console snippet — it must start with { and contain access_token.",
    );
  }

  const identity = await loadIdentity(accessToken);
  return {
    refreshToken,
    accessToken,
    accessTokenExpiresAt: expiresAt,
    entryId: identity.entryId,
    name: identity.name,
    playerName: identity.playerName,
  };
}

/** @deprecated FPL retired users.premierleague.com */
export async function loginWithPassword(_email: string, _password: string): Promise<FplSession> {
  throw new Error(
    "Email/password sign-in no longer works. Paste your oidc.user JSON from the browser instead.",
  );
}

export async function loginWithCookie(raw: string): Promise<FplSession> {
  return loginWithRefreshToken(raw);
}

async function ensureAccessToken(session: FplSession): Promise<{
  accessToken: string;
  session: FplSession;
}> {
  if (
    session.accessToken &&
    session.accessTokenExpiresAt &&
    Date.now() < session.accessTokenExpiresAt
  ) {
    return { accessToken: session.accessToken, session };
  }

  // Access present but expiry unknown — try it once.
  if (session.accessToken && !session.accessTokenExpiresAt && !session.refreshToken) {
    return { accessToken: session.accessToken, session };
  }

  if (!session.refreshToken) {
    throw new Error(
      "Session expired. Sign in again with a fresh oidc.user paste from fantasy.premierleague.com.",
    );
  }

  try {
    const tokens = await exchangeRefreshToken(session.refreshToken);
    const next: FplSession = {
      ...session,
      refreshToken: tokens.refreshToken,
      accessToken: tokens.accessToken,
      accessTokenExpiresAt: tokens.expiresAt,
    };
    await writeSession(next);
    return { accessToken: tokens.accessToken, session: next };
  } catch (err) {
    if (err instanceof Error && err.message === "invalid_grant") {
      throw new Error(
        "FPL rotated your refresh token. Sign in again with a fresh oidc.user paste.",
      );
    }
    throw err;
  }
}

export async function fplAuthed(
  path: string,
  init: RequestInit = {},
): Promise<{ ok: true; status: number; data: unknown } | { ok: false; status: number; error: string }> {
  const stored = await readSession();
  if (!stored) return { ok: false, status: 401, error: "Not signed in" };

  let accessToken: string;
  try {
    ({ accessToken } = await ensureAccessToken(stored));
  } catch (err) {
    const message = err instanceof Error ? err.message : "Could not refresh FPL session";
    return { ok: false, status: 401, error: message };
  }

  const headers = new Headers(init.headers);
  headers.set("User-Agent", UA);
  headers.set("Accept", "application/json");
  headers.set("Origin", "https://fantasy.premierleague.com");
  headers.set("Referer", "https://fantasy.premierleague.com/");
  headers.set("X-API-Authorization", `Bearer ${accessToken}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const url = `${FPL}/${path.replace(/^\/+/, "").replace(/\/?$/, "/")}`;
  let res: Response;
  try {
    res = await fetch(url, { ...init, headers, cache: "no-store", redirect: "follow" });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "network error";
    return { ok: false, status: 502, error: `FPL unreachable (${msg})` };
  }

  if (res.status === 401 || res.status === 403) {
    try {
      const retry = await ensureAccessToken({
        ...stored,
        accessToken: undefined,
        accessTokenExpiresAt: 0,
      });
      headers.set("X-API-Authorization", `Bearer ${retry.accessToken}`);
      res = await fetch(url, { ...init, headers, cache: "no-store", redirect: "follow" });
    } catch {
      return { ok: false, status: 401, error: "FPL session expired. Sign in again." };
    }
  }

  const text = await res.text();
  if (!res.ok) {
    return { ok: false, status: res.status, error: summariseFplError(text, res.status) };
  }
  if (!text) return { ok: true, status: res.status, data: null };
  try {
    return { ok: true, status: res.status, data: JSON.parse(text) as unknown };
  } catch {
    return { ok: false, status: 502, error: "FPL returned a non-JSON response" };
  }
}

function summariseFplError(text: string, status: number): string {
  try {
    const json = JSON.parse(text) as Record<string, unknown>;
    if (typeof json.detail === "string") return json.detail;
    if (Array.isArray(json.non_field_errors)) return json.non_field_errors.map(String).join(" ");
    const nested = Object.values(json)
      .flatMap((v) => (Array.isArray(v) ? v : [v]))
      .filter((v) => typeof v === "string")
      .slice(0, 4);
    if (nested.length) return nested.join(" ");
  } catch {
    /* HTML */
  }
  if (status === 401 || status === 403) return "FPL session expired. Sign in again.";
  return `FPL error ${status}`;
}
