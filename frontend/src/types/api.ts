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
};

export type ChatMessage =
  | { id: string; role: "user"; text: string }
  | { id: string; role: "assistant"; data: ChatResult };
