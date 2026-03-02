export type Role = "admin" | "operator" | "viewer" | "user";

export type ApiError = {
  code: string;
  message: string;
  trace_id?: string;
  status?: number;
};

export type LoginResponse = {
  access_token: string;
  token_type: "bearer";
};

export type SessionItem = {
  id: string;
  title: string;
  updated_at: string;
  canon_gen: number;
  canon_game: string | null;
};

export type SessionDetail = {
  id: string;
  title: string;
  canon_gen: number;
  canon_game: string | null;
  turns: TurnItem[];
};

export type TurnItem = {
  id: string;
  turn_index: number;
  user_text: string;
  assistant_text: string;
  created_at: string;
};

export type ChatResponse = {
  turn_id: string;
  turn_index: number;
  assistant_text: string;
  provider_latency_ms: number;
  token_usage: Record<string, number> | null;
};

export type MemoryDebugResponse = {
  query_plan: Array<{ type: string; q: string }>;
  retrieval: Record<string, unknown>;
  prompt_injection: string;
};

export type TimelineEventItem = {
  id: string;
  turn_id: string;
  canon_level: "confirmed" | "implied" | "pending" | "conflict";
  event_text: string;
  consequence_text: string | null;
  actors: string[];
  items: string[];
  location: string | null;
  evidence: Record<string, unknown>;
  created_at: string;
};

export type MetricsSummary = {
  requests_total: number;
  requests_5xx_total: number;
  provider_latency_ms_avg: number;
  vector_hits_total: number;
  timeline_hits_total: number;
  turns_created_total: number;
  conflicts_total: number;
};

export type RecentLogsResponse = {
  path: string;
  lines: string[];
};

export type CanonPokemonItem = {
  id: string;
  dex_no: number;
  slug_id: string;
  name_zh: string;
  name_en: string;
  aliases: string[];
  types: string[];
  generation: number;
};

export type CanonMoveItem = {
  id: string;
  slug_id: string;
  name_zh: string;
  name_en: string;
  aliases: string[];
  type: string;
  category: string;
  power: number | null;
  accuracy: number | null;
  pp: number | null;
  priority: number;
  generation: number;
};

export type TypeChartItem = {
  atk_type: string;
  def_type: string;
  multiplier: number;
};
