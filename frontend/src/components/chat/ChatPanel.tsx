import { useEffect, useRef, useState } from "react";
import type { ChatMessage as ChatMessageType } from "@/types/api";
import { ChatMessage } from "./ChatMessage";
import { ThinkingLoader } from "./ThinkingLoader";

type PendingConfirm = { mutation_token: string; message?: string };

type Props = {
  messages: ChatMessageType[];
  thinking: boolean;
  statusLabel?: string;
  pendingConfirm: PendingConfirm | null;
  onSend: (text: string) => void;
  onConfirmMutation: (mutationToken: string) => void;
  sendDisabled?: boolean;
};

export function ChatPanel({
  messages,
  thinking,
  statusLabel,
  pendingConfirm,
  onSend,
  onConfirmMutation,
  sendDisabled,
}: Props) {
  const [input, setInput] = useState("");
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, thinking, statusLabel]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || sendDisabled) return;
    setInput("");
    onSend(text);
  };

  return (
    <div className="chat-panel">
      <p className="prompt">How can I help you today?</p>
      <div ref={logRef} className="chat-log" role="log" aria-live="polite">
        {messages.map((m) => (
          <ChatMessage key={m.id} message={m} onConfirmMutation={onConfirmMutation} />
        ))}
        {thinking ? <ThinkingLoader statusLabel={statusLabel} /> : null}
      </div>

      {pendingConfirm?.mutation_token ? (
        <div className="confirm-strip" id="confirm-strip">
          <p className="confirm-strip-title">Pending change — review the message above, then confirm.</p>
          <div className="confirm-bar">
            <p className="confirm-hint muted">
              Review the preview, then confirm to send this update/delete to apex-dev.
            </p>
            <button
              type="button"
              className="btn-confirm-mutation"
              onClick={() => onConfirmMutation(pendingConfirm.mutation_token)}
            >
              Confirm update/delete
            </button>
          </div>
        </div>
      ) : null}

      <form className="chat-form" onSubmit={submit}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Search events, ask about venues, org setup…"
          autoComplete="off"
          disabled={sendDisabled}
        />
        <button type="submit" disabled={sendDisabled}>Send</button>
      </form>
    </div>
  );
}
