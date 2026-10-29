import type { ChatMessage as ChatMessageType, StackStatus, UserProfile } from "@/types/api";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { StackContextBar } from "@/components/StackContextBar";

type PendingConfirm = { mutation_token: string; message?: string };

type Props = {
  profile: UserProfile;
  region: string;
  showRegionPicker: boolean;
  regions: { id: string; label: string }[];
  regionDraft: string;
  messages: ChatMessageType[];
  thinking: boolean;
  statusLabel?: string;
  pendingConfirm: PendingConfirm | null;
  sendDisabled?: boolean;
  onNewChat: () => void;
  onLogout: () => void;
  onOpenRegionPicker: () => void;
  onRegionDraftChange: (v: string) => void;
  onSaveRegion: () => void;
  onSend: (text: string) => void;
  onConfirmMutation: (token: string) => void;
  stackStatus?: StackStatus | null;
};

export function MainScreen({
  profile,
  region,
  showRegionPicker,
  regions,
  regionDraft,
  messages,
  thinking,
  statusLabel,
  pendingConfirm,
  sendDisabled,
  onNewChat,
  onLogout,
  onOpenRegionPicker,
  onRegionDraftChange,
  onSaveRegion,
  onSend,
  onConfirmMutation,
  stackStatus,
}: Props) {
  return (
    <section className="card" id="screen-main">
      <header className="topbar">
        <div>
          <h2 id="welcome-title">Welcome, {profile.name || "APEX User"}</h2>
          <p className="muted" id="welcome-sub">
            Signed in to {profile.tenant || "apex-dev"}.
          </p>
        </div>
        <div className="topbar-actions">
          <button type="button" className="ghost" onClick={onNewChat}>New chat</button>
          <button type="button" className="ghost" onClick={onLogout}>Sign out</button>
        </div>
      </header>

      <div className="profile">
        <p><strong>Profile</strong></p>
        <p className="muted" id="profile-email">{profile.email || profile.userId || ""}</p>
        <p id="profile-region">Region: {region}</p>
        <button type="button" className="link" onClick={onOpenRegionPicker}>Change region</button>
      </div>

      {showRegionPicker ? (
        <div className="region-picker" id="region-picker">
          <label htmlFor="region-main">Region</label>
          <select
            id="region-main"
            value={regionDraft}
            onChange={(e) => onRegionDraftChange(e.target.value)}
          >
            {regions.map((r) => (
              <option key={r.id} value={r.id}>{r.label}</option>
            ))}
          </select>
          <button type="button" onClick={onSaveRegion}>Save</button>
        </div>
      ) : null}

      <StackContextBar region={region} stackStatus={stackStatus} />

      <ChatPanel
        messages={messages}
        thinking={thinking}
        statusLabel={statusLabel}
        pendingConfirm={pendingConfirm}
        onSend={onSend}
        onConfirmMutation={onConfirmMutation}
        sendDisabled={sendDisabled}
      />
    </section>
  );
}
