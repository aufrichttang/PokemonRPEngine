import { apiBaseUrl, apiRequest } from "@/lib/api/client";
import { getToken } from "@/lib/auth/token";
import {
  CanonMoveItem,
  CanonPokemonItem,
  ChatResponse,
  LoginResponse,
  MemoryDebugResponse,
  MetricsSummary,
  RecentLogsResponse,
  SessionDetail,
  SessionItem,
  TimelineEventItem,
  TypeChartItem,
} from "@/lib/schemas/types";
import { parseSseStream } from "@/lib/sse/parseSse";

export async function login(email: string, password: string): Promise<LoginResponse> {
  return apiRequest<LoginResponse>("/v1/auth/login", {
    method: "POST",
    auth: false,
    body: { email, password },
  });
}

export async function register(email: string, password: string): Promise<{ id: string }> {
  return apiRequest<{ id: string }>("/v1/auth/register", {
    method: "POST",
    auth: false,
    body: { email, password },
  });
}

export async function listSessions(page = 1, size = 20): Promise<SessionItem[]> {
  const data = await apiRequest<{ items: SessionItem[] }>(`/v1/sessions?page=${page}&size=${size}`);
  return data.items;
}

export async function createSession(payload: {
  title: string;
  canon_gen: number;
  canon_game: string | null;
  custom_lore_enabled: boolean;
}): Promise<{ id: string }> {
  return apiRequest<{ id: string }>("/v1/sessions", {
    method: "POST",
    body: payload,
  });
}

export async function deleteSession(sessionId: string): Promise<{ ok: boolean }> {
  return apiRequest<{ ok: boolean }>(`/v1/sessions/${sessionId}`, { method: "DELETE" });
}

export async function getSessionDetail(sessionId: string): Promise<SessionDetail> {
  return apiRequest<SessionDetail>(`/v1/sessions/${sessionId}`);
}

export async function sendMessage(
  sessionId: string,
  text: string,
  stream = false,
): Promise<ChatResponse> {
  return apiRequest<ChatResponse>(`/v1/sessions/${sessionId}/messages`, {
    method: "POST",
    body: { text, stream },
  });
}

export async function streamMessage(
  sessionId: string,
  text: string,
  onDelta: (chunk: string) => void,
): Promise<{ turn_id: string; turn_index: number; usage: Record<string, number> }> {
  const token = getToken();
  const timeoutMs = Number(process.env.NEXT_PUBLIC_STREAM_CONNECT_TIMEOUT_MS ?? "15000");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}/v1/sessions/${sessionId}/messages`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ text, stream: true }),
      signal: controller.signal,
    });
  } catch (err) {
    const msg =
      err instanceof DOMException && err.name === "AbortError"
        ? `stream connect timeout after ${timeoutMs}ms`
        : err instanceof Error
          ? err.message
          : "stream request failed";
    throw new Error(msg);
  } finally {
    clearTimeout(timeout);
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const error = payload?.error as { code?: string; message?: string; trace_id?: string } | undefined;
    if (error?.message) {
      throw new Error(
        error.trace_id
          ? `${error.message} (code=${error.code ?? "stream_http_error"}, trace=${error.trace_id})`
          : `${error.message} (code=${error.code ?? "stream_http_error"})`,
      );
    }
    throw new Error(`stream request failed (status=${response.status})`);
  }

  let donePayload: { turn_id: string; turn_index: number; usage: Record<string, number> } | null =
    null;
  await parseSseStream(response, (event) => {
    if (event.event === "delta") {
      onDelta(String(event.data?.text ?? ""));
    } else if (event.event === "done") {
      donePayload = {
        turn_id: String(event.data?.turn_id ?? ""),
        turn_index: Number(event.data?.turn_index ?? 0),
        usage: (event.data?.usage as Record<string, number>) ?? {},
      };
    } else if (event.event === "error") {
      const code = String(event.data?.code ?? "stream_error");
      const msg = String(event.data?.message ?? "stream error");
      throw new Error(`${msg} (code=${code})`);
    }
  });
  if (!donePayload) throw new Error("stream ended without done event");
  return donePayload;
}

export async function getMemoryDebug(sessionId: string): Promise<MemoryDebugResponse> {
  return apiRequest<MemoryDebugResponse>(`/v1/sessions/${sessionId}/memory/debug`);
}

export async function listTimelineEvents(
  sessionId: string,
  canonLevel?: "confirmed" | "implied" | "pending" | "conflict",
): Promise<TimelineEventItem[]> {
  const query = canonLevel ? `?canon_level=${canonLevel}` : "";
  const data = await apiRequest<{ items: TimelineEventItem[] }>(
    `/v1/sessions/${sessionId}/timeline/events${query}`,
  );
  return data.items;
}

export async function confirmTimelineEvent(
  sessionId: string,
  eventId: string,
  note: string,
): Promise<{ event_id: string; canon_level: string }> {
  return apiRequest<{ event_id: string; canon_level: string }>(
    `/v1/sessions/${sessionId}/memory/confirm`,
    {
      method: "POST",
      body: { event_id: eventId, confirm: true, note },
    },
  );
}

export async function getMetricsSummary(): Promise<MetricsSummary> {
  return apiRequest<MetricsSummary>("/v1/admin/metrics/summary");
}

export async function getRecentLogs(lines = 200): Promise<RecentLogsResponse> {
  return apiRequest<RecentLogsResponse>(`/v1/admin/logs/recent?lines=${lines}`);
}

export async function getHealth(): Promise<{ status: string }> {
  return apiRequest<{ status: string }>("/healthz", { auth: false });
}

export async function getReady(): Promise<{ status: string }> {
  return apiRequest<{ status: string }>("/readyz", { auth: false });
}

export async function listCanonPokemon(params: {
  q?: string;
  generation?: number;
  page?: number;
  size?: number;
}): Promise<CanonPokemonItem[]> {
  const usp = new URLSearchParams();
  if (params.q) usp.set("q", params.q);
  if (params.generation) usp.set("generation", String(params.generation));
  usp.set("page", String(params.page ?? 1));
  usp.set("size", String(params.size ?? 20));
  const data = await apiRequest<{ items: CanonPokemonItem[] }>(`/v1/canon/pokemon?${usp.toString()}`);
  return data.items;
}

export async function listCanonMoves(params: {
  q?: string;
  generation?: number;
  page?: number;
  size?: number;
}): Promise<CanonMoveItem[]> {
  const usp = new URLSearchParams();
  if (params.q) usp.set("q", params.q);
  if (params.generation) usp.set("generation", String(params.generation));
  usp.set("page", String(params.page ?? 1));
  usp.set("size", String(params.size ?? 20));
  const data = await apiRequest<{ items: CanonMoveItem[] }>(`/v1/canon/moves?${usp.toString()}`);
  return data.items;
}

export async function getTypeChart(generation = 9): Promise<TypeChartItem[]> {
  const data = await apiRequest<{ items: TypeChartItem[] }>(
    `/v1/canon/type-chart?generation=${generation}`,
  );
  return data.items;
}
