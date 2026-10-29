import type { UserProfile } from "@/types/api";

export const STORAGE_TOKEN = "apex_ai_token";
export const STORAGE_REGION = "apex_ai_region";
export const STORAGE_PROFILE = "apex_ai_profile";
export const STORAGE_SESSION_ID = "apex_ai_session_id";
export const STORAGE_PENDING_CHAT = "apex_ai_pending_confirm";
export const STORAGE_LAST_QUERY = "apex_ai_last_query";
export const STORAGE_PENDING_RERUN = "apex_ai_pending_rerun";

export type PendingRerun = { message: string; region: string };

export function getToken(): string {
  return sessionStorage.getItem(STORAGE_TOKEN) || "";
}

export function setSession(token: string, region: string, profile: UserProfile) {
  sessionStorage.setItem(STORAGE_TOKEN, token);
  sessionStorage.setItem(STORAGE_REGION, region);
  sessionStorage.setItem(STORAGE_PROFILE, JSON.stringify(profile));
}

export function clearAuthSession() {
  sessionStorage.removeItem(STORAGE_TOKEN);
  sessionStorage.removeItem(STORAGE_REGION);
  sessionStorage.removeItem(STORAGE_PROFILE);
  sessionStorage.removeItem(STORAGE_SESSION_ID);
}

export function clearSession() {
  clearAuthSession();
  sessionStorage.removeItem(STORAGE_PENDING_CHAT);
  sessionStorage.removeItem(STORAGE_LAST_QUERY);
  sessionStorage.removeItem(STORAGE_PENDING_RERUN);
}

export function saveLastQuery(message: string, region: string) {
  const text = message.trim();
  if (!text) return;
  sessionStorage.setItem(STORAGE_LAST_QUERY, JSON.stringify({ message: text, region }));
}

export function readPendingRerun(): PendingRerun | null {
  try {
    return JSON.parse(sessionStorage.getItem(STORAGE_PENDING_RERUN) || "null") as PendingRerun | null;
  } catch {
    return null;
  }
}

export function setPendingRerunFromLast(rerunMessage?: string | null, rerunRegion?: string) {
  let payload: PendingRerun | null = null;
  if (rerunMessage?.trim()) {
    payload = { message: rerunMessage.trim(), region: rerunRegion || "US-West" };
  } else {
    try {
      payload = JSON.parse(sessionStorage.getItem(STORAGE_LAST_QUERY) || "null") as PendingRerun | null;
    } catch {
      payload = null;
    }
  }
  if (payload?.message) {
    sessionStorage.setItem(STORAGE_PENDING_RERUN, JSON.stringify(payload));
  }
}

export function clearPendingRerun() {
  sessionStorage.removeItem(STORAGE_PENDING_RERUN);
}

export function getOrCreateSessionId(): string {
  let id = sessionStorage.getItem(STORAGE_SESSION_ID);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(STORAGE_SESSION_ID, id);
  }
  return id;
}

export function newChatSession(): string {
  const id = crypto.randomUUID();
  sessionStorage.setItem(STORAGE_SESSION_ID, id);
  sessionStorage.removeItem(STORAGE_PENDING_CHAT);
  return id;
}

export function decodeJwtPayload(token: string): { exp?: number } | null {
  try {
    const segment = token.split(".")[1];
    if (!segment) return null;
    const padded = segment.replace(/-/g, "+").replace(/_/g, "/");
    const json = atob(padded.padEnd(padded.length + ((4 - (padded.length % 4)) % 4), "="));
    return JSON.parse(json) as { exp?: number };
  } catch {
    return null;
  }
}

export function isTokenExpired(token: string, skewSeconds = 30): boolean {
  const payload = decodeJwtPayload(token);
  if (!payload?.exp) return false;
  return Date.now() / 1000 >= payload.exp - skewSeconds;
}
