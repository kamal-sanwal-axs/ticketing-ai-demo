import type { ChatResult, Region, UserProfile } from "@/types/api";

export async function fetchRegions(): Promise<Region[]> {
  const res = await fetch("/api/regions");
  if (!res.ok) throw new Error("Failed to load regions");
  return res.json() as Promise<Region[]>;
}

export async function loginRequest(token: string, region: string) {
  const res = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, region }),
  });
  return res.json() as Promise<{ ok: boolean; profile: UserProfile; message?: string }>;
}

export async function fetchProfile(token: string, region: string): Promise<UserProfile> {
  const res = await fetch(`/api/profile?region=${encodeURIComponent(region)}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Profile fetch failed");
  return res.json() as Promise<UserProfile>;
}

export async function fetchStackStatus(region: string) {
  const q = region ? `?region=${encodeURIComponent(region)}` : "";
  const res = await fetch(`/api/ui/stack${q}`);
  if (!res.ok) throw new Error("Stack status unavailable");
  return res.json() as Promise<import("@/types/api").StackStatus>;
}

function authErrorMessage(res: Response, errBody: { detail?: unknown; message?: string }) {
  const detail = errBody?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => (typeof d === "object" && d && "msg" in d ? String(d.msg) : JSON.stringify(d))).join("; ");
  }
  return errBody?.message || res.statusText || "Unauthorized";
}

export async function consumeChatSse(response: Response, onStatus?: (label: string) => void): Promise<ChatResult | null> {
  const reader = response.body?.getReader();
  if (!reader) return null;
  const decoder = new TextDecoder();
  let buffer = "";
  let result: ChatResult | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const block of parts) {
      const lines = block.split("\n");
      let event = "message";
      let data = "";
      for (const line of lines) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      const parsed = JSON.parse(data) as ChatResult & { label?: string; message?: string };
      if (event === "status" && parsed.label) onStatus?.(parsed.label);
      else if (event === "result") result = parsed;
      else if (event === "error") throw new Error(parsed.message || "Stream error");
    }
  }
  return result;
}

export async function streamChat(
  token: string,
  body: {
    message: string;
    region: string;
    session_id: string;
    confirm_mutation?: boolean;
    mutation_token?: string | null;
  },
  onStatus?: (label: string) => void,
): Promise<ChatResult> {
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw Object.assign(new Error(authErrorMessage(res, err)), { status: res.status, detail: err });
  }
  const data = await consumeChatSse(res, onStatus);
  if (!data) throw new Error("Empty stream response");
  return data;
}
