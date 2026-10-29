import type { ChatMessage as ChatMessageType, ChatResult } from "@/types/api";
import { DisplayView } from "@/components/display/DisplayView";

type Props = {
  message: ChatMessageType;
  onConfirmMutation?: (token: string) => void;
};

function ConfirmBar({ onConfirm }: { onConfirm: () => void }) {
  return (
    <div className="confirm-bar">
      <p className="confirm-hint muted">
        Review the preview, then confirm to send this update/delete to apex-dev.
      </p>
      <button type="button" className="btn-confirm-mutation" onClick={onConfirm}>
        Confirm update/delete
      </button>
    </div>
  );
}

function AssistantBody({ data, onConfirmMutation }: { data: ChatResult; onConfirmMutation?: (t: string) => void }) {
  const mutationToken =
    data.mutation_token || data.display?.pending_confirmation?.mutation_token || null;

  return (
    <>
      {data.semantic_routing?.label ? (
        <div className="msg-meta semantic-routing">
          <span className="intent-pill muted">{data.semantic_routing.label}</span>
        </div>
      ) : null}
      {data.intent ? (
        <div className="msg-meta">
          <span className="intent-pill">{data.intent.replace(/_/g, " ")}</span>
        </div>
      ) : null}
      {data.display ? (
        <>
          <DisplayView display={data.display} />
          {data.requires_confirmation && mutationToken && onConfirmMutation ? (
            <ConfirmBar onConfirm={() => onConfirmMutation(mutationToken)} />
          ) : null}
          {data.answer &&
          (data.display.type === "table" || data.error || data.display.level === "error") ? (
            <p className="msg-summary muted">{data.answer}</p>
          ) : null}
        </>
      ) : (
        <p className="msg-body">{data.answer || "No response."}</p>
      )}
    </>
  );
}

export function ChatMessage({ message, onConfirmMutation }: Props) {
  if (message.role === "user") {
    return (
      <div className="msg user">
        <span className="msg-label">You</span>
        <p className="msg-body">{message.text}</p>
      </div>
    );
  }

  const data = message.data;
  const isError = data.error;

  return (
    <div className={`msg bot ${isError ? "msg-error" : ""}`}>
      <span className="msg-label">Assistant</span>
      <AssistantBody data={data} onConfirmMutation={onConfirmMutation} />
    </div>
  );
}
