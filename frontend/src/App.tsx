import { useCallback, useEffect, useState } from "react";
import { fetchProfile, fetchRegions, loginRequest, streamChat } from "@/api/client";
import { AppFooter } from "@/components/AppFooter";
import { LoginScreen } from "@/components/LoginScreen";
import { MainScreen } from "@/components/MainScreen";
import {
  STORAGE_PENDING_CHAT,
  STORAGE_PROFILE,
  STORAGE_REGION,
  clearAuthSession,
  clearPendingRerun,
  clearSession,
  getOrCreateSessionId,
  getToken,
  isTokenExpired,
  newChatSession,
  readPendingRerun,
  saveLastQuery,
  setPendingRerunFromLast,
  setSession,
} from "@/lib/session";
import type { ChatMessage, ChatResult, Region, UserProfile } from "@/types/api";
import type { PendingRerun } from "@/lib/session";

function nextId() {
  return crypto.randomUUID();
}

export function App() {
  const [regions, setRegions] = useState<Region[]>([]);
  const [authenticated, setAuthenticated] = useState(false);
  const [profile, setProfile] = useState<UserProfile>({});
  const [region, setRegion] = useState("US-West");
  const [loginToken, setLoginToken] = useState("");
  const [loginRegion, setLoginRegion] = useState("US-West");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loginBusy, setLoginBusy] = useState(false);
  const [showRegionPicker, setShowRegionPicker] = useState(false);
  const [regionDraft, setRegionDraft] = useState("US-West");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [thinking, setThinking] = useState(false);
  const [statusLabel, setStatusLabel] = useState<string | undefined>();
  const [pendingConfirm, setPendingConfirm] = useState<{ mutation_token: string; message?: string } | null>(null);
  const [pendingRerun, setPendingRerun] = useState<PendingRerun | null>(() => readPendingRerun());
  const [rerunAfterLogin, setRerunAfterLogin] = useState(true);

  useEffect(() => {
    if (!authenticated) {
      setPendingRerun(readPendingRerun());
    }
  }, [authenticated]);

  useEffect(() => {
    document.body.classList.toggle("layout-chat", authenticated);
  }, [authenticated]);

  useEffect(() => {
    fetchRegions()
      .then((r) => {
        setRegions(r);
        if (r.length) {
          setLoginRegion(r[0].id);
          setRegionDraft(r[0].id);
        }
      })
      .catch(() => {});
  }, []);

  const redirectToLogin = useCallback((message?: string, options?: { rerunMessage?: string; rerunRegion?: string }) => {
    setPendingRerunFromLast(options?.rerunMessage, options?.rerunRegion);
    clearAuthSession();
    setPendingRerun(readPendingRerun());
    setAuthenticated(false);
    setLoginToken("");
    setLoginError(message || "Your session expired. Sign in again with a fresh token from apex-dev.");
  }, []);

  const logout = useCallback(() => {
    clearSession();
    setAuthenticated(false);
    setMessages([]);
    setPendingConfirm(null);
    setPendingRerun(null);
    setLoginToken("");
    setLoginError(null);
  }, []);

  const restoreSession = useCallback(async () => {
    const token = getToken();
    if (!token) return;
    if (isTokenExpired(token)) {
      redirectToLogin("Your access token expired. Paste a new JWT from apex-dev.");
      return;
    }
    const storedRegion = sessionStorage.getItem(STORAGE_REGION) || "US-West";
    let cached: UserProfile = {};
    try {
      cached = JSON.parse(sessionStorage.getItem(STORAGE_PROFILE) || "{}") as UserProfile;
    } catch {
      cached = { name: "APEX User" };
    }
    try {
      const fresh = await fetchProfile(token, storedRegion);
      cached = fresh;
      sessionStorage.setItem(STORAGE_PROFILE, JSON.stringify(fresh));
    } catch {
      /* keep cached */
    }
    setProfile(cached);
    setRegion(storedRegion);
    setRegionDraft(storedRegion);
    setAuthenticated(true);
  }, [redirectToLogin]);

  useEffect(() => {
    restoreSession();
  }, [restoreSession]);

  const handleLogin = async () => {
    const token = loginToken.trim().replace(/^Bearer\s+/i, "");
    setLoginError(null);
    if (!token) {
      setLoginError("Token is required.");
      return;
    }
    setLoginBusy(true);
    try {
      const data = await loginRequest(token, loginRegion);
      if (!data.ok) {
        setLoginError(data.message || "Login failed.");
        return;
      }
      setSession(token, loginRegion, data.profile);
      setProfile(data.profile);
      setRegion(loginRegion);
      setRegionDraft(loginRegion);
      setAuthenticated(true);

      const pending = readPendingRerun();
      if (rerunAfterLogin && pending?.message) {
        clearPendingRerun();
        setPendingRerun(null);
        const rerunRegion = pending.region || loginRegion;
        if (rerunRegion !== loginRegion) {
          sessionStorage.setItem(STORAGE_REGION, rerunRegion);
          setRegion(rerunRegion);
          setRegionDraft(rerunRegion);
        }
        await sendChat(pending.message, { skipUserEcho: true });
      } else {
        clearPendingRerun();
        setPendingRerun(null);
      }
    } catch (e) {
      setLoginError(String(e));
    } finally {
      setLoginBusy(false);
    }
  };

  const sendChat = async (
    message: string,
    options: { confirm_mutation?: boolean; mutation_token?: string | null; skipUserEcho?: boolean } = {},
  ) => {
    const token = getToken();
    if (!token || isTokenExpired(token)) {
      redirectToLogin("Your access token expired. Paste a new JWT from apex-dev.", {
        rerunMessage: message,
        rerunRegion: region,
      });
      return;
    }
    const confirm_mutation = Boolean(options.confirm_mutation);
    const mutation_token = options.mutation_token || null;
    const session_id = getOrCreateSessionId();

    if (!options.skipUserEcho) {
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "user", text: confirm_mutation ? `Confirm: ${message}` : message },
      ]);
    }

    if (!confirm_mutation) {
      saveLastQuery(message, region);
      sessionStorage.setItem(
        STORAGE_PENDING_CHAT,
        JSON.stringify({ message, region, mutation_token: null }),
      );
    }

    setThinking(true);
    setStatusLabel(undefined);
    try {
      const data = await streamChat(
        token,
        { message, region, session_id, confirm_mutation, mutation_token },
        (label) => setStatusLabel(label),
      );
      if (data.session_id) sessionStorage.setItem("apex_ai_session_id", data.session_id);

      if (data.requires_confirmation && data.mutation_token) {
        sessionStorage.setItem(
          STORAGE_PENDING_CHAT,
          JSON.stringify({ message, region, mutation_token: data.mutation_token }),
        );
        setPendingConfirm({ mutation_token: data.mutation_token, message });
      } else if (confirm_mutation) {
        sessionStorage.removeItem(STORAGE_PENDING_CHAT);
        setPendingConfirm(null);
      } else if (!data.requires_confirmation) {
        setPendingConfirm(null);
      }

      setMessages((prev) => [...prev, { id: nextId(), role: "assistant", data }]);
    } catch (e) {
      const err = e as Error & { status?: number; detail?: { detail?: string } };
      if (err.status === 401) {
        redirectToLogin(err.message, { rerunMessage: message, rerunRegion: region });
        return;
      }
      const fail: ChatResult = {
        answer: err.message,
        display: {
          type: "article",
          title: "Error",
          level: "error",
          paragraphs: [err.message],
        },
        error: true,
      };
      setMessages((prev) => [...prev, { id: nextId(), role: "assistant", data: fail }]);
    } finally {
      setThinking(false);
    }
  };

  const handleConfirmMutation = (mutationToken: string) => {
    let pending: { message?: string; mutation_token?: string } | null = null;
    try {
      pending = JSON.parse(sessionStorage.getItem(STORAGE_PENDING_CHAT) || "null");
    } catch {
      pending = null;
    }
    const message = pending?.message;
    const token = mutationToken || pending?.mutation_token;
    if (!message || !token) return;
    sendChat(message, { confirm_mutation: true, mutation_token: token });
  };

  return (
    <div className="page-shell">
      <div id="app">
        {!authenticated ? (
          <LoginScreen
            regions={regions}
            token={loginToken}
            region={loginRegion}
            error={loginError}
            busy={loginBusy}
            pendingRerun={pendingRerun}
            rerunAfterLogin={rerunAfterLogin}
            onRerunAfterLoginChange={setRerunAfterLogin}
            onTokenChange={setLoginToken}
            onRegionChange={setLoginRegion}
            onSubmit={handleLogin}
          />
        ) : (
          <MainScreen
            profile={profile}
            region={region}
            showRegionPicker={showRegionPicker}
            regions={regions}
            regionDraft={regionDraft}
            messages={messages}
            thinking={thinking}
            statusLabel={statusLabel}
            pendingConfirm={pendingConfirm}
            sendDisabled={thinking}
            onNewChat={() => {
              newChatSession();
              setMessages([]);
              setPendingConfirm(null);
            }}
            onLogout={logout}
            onOpenRegionPicker={() => setShowRegionPicker(true)}
            onRegionDraftChange={setRegionDraft}
            onSaveRegion={() => {
              sessionStorage.setItem(STORAGE_REGION, regionDraft);
              setRegion(regionDraft);
              setShowRegionPicker(false);
            }}
            onSend={(text) => sendChat(text)}
            onConfirmMutation={handleConfirmMutation}
          />
        )}
      </div>
      <AppFooter />
    </div>
  );
}
