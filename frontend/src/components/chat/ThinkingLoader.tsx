type Props = { statusLabel?: string };

export function ThinkingLoader({ statusLabel }: Props) {
  return (
    <div className="msg bot thinking" aria-busy="true" aria-live="polite">
      <span className="msg-label">Assistant</span>
      <div className="thinking-body">
        <span className="thinking-text">Working</span>
        <span className="thinking-dots" aria-hidden="true">…</span>
      </div>
      <p className="thinking-sub muted">
        {statusLabel ||
          "Routing, retrieving context, and calling APEX APIs — this can take a few seconds."}
      </p>
    </div>
  );
}
