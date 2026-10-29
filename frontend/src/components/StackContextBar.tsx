import { useCallback, useEffect, useState } from "react";
import { fetchStackStatus } from "@/api/client";
import type { StackStatus } from "@/types/api";

type Props = {
  region: string;
  stackStatus?: StackStatus | null;
};

export function StackContextBar({ region, stackStatus: stackFromChat }: Props) {
  const [stack, setStack] = useState<StackStatus | null>(stackFromChat ?? null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (stackFromChat) {
      setStack(stackFromChat);
      return;
    }
  }, [stackFromChat]);

  const refresh = useCallback(() => {
    fetchStackStatus(region)
      .then(setStack)
      .catch(() => {});
  }, [region]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  if (!stack) {
    return (
      <div className="stack-context-bar muted" aria-live="polite">
        Loading stack…
      </div>
    );
  }

  const last = stack.last_llm_context;
  const ctxUsed =
    stack.context_percent_used ??
    last?.percent_used ??
    (last?.percent_left != null ? 100 - last.percent_left : null);
  const summary = stack.bar_label || [
    stack.chat_model_label,
    ctxUsed != null ? `${ctxUsed}% ctx used` : "ctx —",
    `${stack.sources_count} sources`,
    region || stack.environment,
  ].join(" · ");

  return (
    <div className="stack-context-wrap">
      <button
        type="button"
        className="stack-context-bar"
        aria-expanded={expanded}
        aria-controls="stack-context-details"
        title="LLM model and context budget (click for details)"
        onClick={() => setExpanded((v) => !v)}
      >
        <span className="stack-context-summary">{summary}</span>
        <span className="stack-context-chevron" aria-hidden>
          {expanded ? "▾" : "▸"}
        </span>
      </button>
      {expanded ? (
        <div className="stack-context-details" id="stack-context-details">
          <dl>
            <div>
              <dt>Chat model</dt>
              <dd>{stack.chat_model || stack.chat_model_label}</dd>
            </div>
            <div>
              <dt>Embed</dt>
              <dd>
                {stack.embed_backend} · {stack.embed_model}
              </dd>
            </div>
            <div>
              <dt>Rerank</dt>
              <dd>{stack.rerank_model || "—"}</dd>
            </div>
            <div>
              <dt>Context budget</dt>
              <dd>
                synthesis {stack.context_budget_tokens?.toLocaleString()} tok · routing{" "}
                {stack.context_routing_budget_tokens?.toLocaleString()} tok
              </dd>
            </div>
            {last ? (
              <div>
                <dt>Last LLM call</dt>
                <dd>
                  ~{last.estimated_tokens?.toLocaleString()} / {last.budget_tokens?.toLocaleString()} tok (
                  {last.percent_used ?? (last.percent_left != null ? 100 - last.percent_left : "—")}% used
                  {last.routing ? ", routing" : ", synthesis"}
                  {last.prompt_trimmed ? ", trimmed" : ""})
                </dd>
              </div>
            ) : null}
            <div>
              <dt>Indexed sources</dt>
              <dd>
                {stack.tool_count} tools · {stack.kb_chunks} KB chunks · {stack.openapi_sources} OpenAPI
                {stack.kg_enabled ? " · Neo4j KG" : ""} · {stack.vector_store}
              </dd>
            </div>
            <div>
              <dt>Environment</dt>
              <dd>
                {stack.environment}
                {region ? ` · region ${region}` : ""}
              </dd>
            </div>
          </dl>
          <button type="button" className="link stack-context-refresh" onClick={refresh}>
            Refresh
          </button>
        </div>
      ) : null}
    </div>
  );
}
