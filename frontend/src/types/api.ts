export type Region = { id: string; label: string };

export type UserProfile = {
  name?: string;
  email?: string;
  userId?: string;
  tenant?: string;
};

export type DisplayColumn = {
  key: string;
  label: string;
  cellType?: string;
};

export type DisplayChart = {
  title?: string;
  labels?: string[];
  values?: number[];
};

export type DisplaySection = {
  title?: string;
  paragraphs?: string[];
  fields?: { label: string; value?: string | number | null }[];
  items?: string[];
  links?: { label: string; href: string; note?: string }[];
  table?: { columns: DisplayColumn[]; rows: Record<string, unknown>[] };
};

export type UiDisplay = {
  type?: string;
  level?: string;
  badge?: string;
  title?: string;
  subtitle?: string;
  columns?: DisplayColumn[];
  rows?: Record<string, unknown>[];
  count?: number;
  charts?: DisplayChart[];
  sections?: DisplaySection[];
  fields?: { label: string; value?: string | number | null }[];
  paragraphs?: string[];
  items?: string[];
  itemsTitle?: string;
  footnote?: string;
  citations?: { label?: string; href?: string; status?: string }[];
  pending_confirmation?: { mutation_token?: string };
  sandbox_html?: string;
};

export type ChatResult = {
  answer: string;
  intent?: string;
  display?: UiDisplay | null;
  requires_confirmation?: boolean;
  mutation_token?: string | null;
  session_id?: string;
  memory_source?: string | null;
  error?: boolean;
  error_code?: string | null;
  error_message?: string | null;
  semantic_routing?: { label?: string };
  stack_status?: StackStatus | null;
};

export type StackStatus = {
  environment?: string;
  region?: string;
  chat_model?: string;
  chat_model_label?: string;
  embed_model?: string;
  embed_backend?: string;
  rerank_model?: string;
  vector_store?: string;
  kg_enabled?: boolean;
  context_budget_tokens?: number;
  context_routing_budget_tokens?: number;
  context_percent_used?: number | null;
  tool_count?: number;
  kb_chunks?: number;
  openapi_sources?: number;
  sources_count?: number;
  bar_label?: string;
  last_llm_context?: {
    estimated_tokens?: number;
    budget_tokens?: number;
    percent_used?: number;
    percent_left?: number;
    routing?: boolean;
    prompt_trimmed?: boolean;
    model?: string;
  } | null;
};

export type ChatMessage =
  | { id: string; role: "user"; text: string }
  | { id: string; role: "assistant"; data: ChatResult };
