import { apiBaseUrl, apiRequest } from "@/lib/api/client";
import { getToken } from "@/lib/auth/token";
import {
  ActionOptionV2,
  FactionKernelState,
  GameSlot,
  GameSlotItem,
  GameTurnResponse,
  LoreKernelState,
  TimeKernelState,
} from "@/lib/schemas/types";
import { parseSseStream } from "@/lib/sse/parseSse";

type Pace = "fast" | "balanced" | "epic";

type StreamHandlers = {
  onAck?: (payload: Record<string, unknown>) => void;
  onPrimary?: (text: string) => void;
  onDelta?: (text: string) => void;
  onProgress?: (payload: Record<string, unknown>) => void;
  onDone?: (payload: GameTurnResponse) => void;
};

const JSON_STREAM_MARKERS = [
  "<!--json-->",
  "<!--/json-->",
  "```json",
  "```",
  '"facts_used"',
  '"state_update"',
  '"open_threads_update"',
  '"action_options"',
  '"kernel_delta_summary"',
  '"state_snapshot"',
];

function sanitizeStreamingDelta(
  text: string,
  state: { blocked: boolean; carry: string },
): string {
  if (!text) return "";
  if (state.blocked) return "";

  const merged = `${state.carry}${text}`;
  const lowered = merged.toLowerCase();

  let markerIndex = -1;
  for (const marker of JSON_STREAM_MARKERS) {
    const idx = lowered.indexOf(marker);
    if (idx >= 0 && (markerIndex < 0 || idx < markerIndex)) {
      markerIndex = idx;
    }
  }

  if (markerIndex >= 0) {
    state.blocked = true;
    state.carry = "";
    return merged.slice(0, markerIndex).replace(/\s+$/g, "");
  }

  state.carry = merged.slice(-56);
  return text;
}

export async function listGameSlots(page = 1, size = 50): Promise<GameSlotItem[]> {
  const data = await apiRequest<{ items: GameSlotItem[] }>(`/v2/game/slots?page=${page}&size=${size}`);
  return data.items;
}

export async function createGameSlot(payload: {
  slot_name: string;
  world_seed?: string | null;
  canon_gen: number;
  canon_game?: string | null;
  player_profile?: Record<string, unknown>;
}): Promise<GameSlot> {
  return apiRequest<GameSlot>("/v2/game/slots", {
    method: "POST",
    body: payload,
  });
}

export async function getGameSlot(slotId: string): Promise<GameSlot> {
  return apiRequest<GameSlot>(`/v2/game/slots/${slotId}`);
}

export async function getGameLore(slotId: string): Promise<{ slot_id: string; lore_kernel: LoreKernelState }> {
  return apiRequest<{ slot_id: string; lore_kernel: LoreKernelState }>(`/v2/game/slots/${slotId}/lore`);
}

export async function getGameTime(slotId: string): Promise<{ slot_id: string; time_kernel: TimeKernelState }> {
  return apiRequest<{ slot_id: string; time_kernel: TimeKernelState }>(`/v2/game/slots/${slotId}/time`);
}

export async function getGameFactions(
  slotId: string,
): Promise<{ slot_id: string; faction_kernel: FactionKernelState }> {
  return apiRequest<{ slot_id: string; faction_kernel: FactionKernelState }>(
    `/v2/game/slots/${slotId}/factions`,
  );
}

export async function sendGameTurn(
  slotId: string,
  text: string,
  language = "zh",
  pace: Pace = "balanced",
  clientTurnId?: string,
): Promise<GameTurnResponse> {
  return apiRequest<GameTurnResponse>(`/v2/game/slots/${slotId}/turns`, {
    method: "POST",
    body: { text, stream: false, language, pace, client_turn_id: clientTurnId },
  });
}

export async function streamGameTurn(
  slotId: string,
  text: string,
  handlers: StreamHandlers = {},
  language = "zh",
  pace: Pace = "balanced",
  clientTurnId?: string,
): Promise<GameTurnResponse> {
  const token = getToken();
  const response = await fetch(`${apiBaseUrl()}/v2/game/slots/${slotId}/turns`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ text, stream: true, language, pace, client_turn_id: clientTurnId }),
  });
  return consumeGameTurnStream(response, handlers);
}

export async function streamGameAction(
  slotId: string,
  actionId: string,
  handlers: StreamHandlers = {},
  language = "zh",
  pace: Pace = "balanced",
  clientTurnId?: string,
): Promise<GameTurnResponse> {
  const token = getToken();
  const response = await fetch(`${apiBaseUrl()}/v2/game/slots/${slotId}/actions/${actionId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ stream: true, language, pace, client_turn_id: clientTurnId }),
  });
  return consumeGameTurnStream(response, handlers);
}

async function consumeGameTurnStream(response: Response, handlers: StreamHandlers): Promise<GameTurnResponse> {
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const error = payload?.error as { code?: string; message?: string; trace_id?: string } | undefined;
    if (error?.message) {
      throw new Error(
        error.trace_id
          ? `${error.message} (code=${error.code ?? "stream_error"}, trace=${error.trace_id})`
          : `${error.message} (code=${error.code ?? "stream_error"})`,
      );
    }
    throw new Error(`stream request failed (status=${response.status})`);
  }

  let donePayload: GameTurnResponse | null = null;
  let stagedOptions: ActionOptionV2[] = [];
  const sanitizeState = { blocked: false, carry: "" };

  await parseSseStream(response, (event) => {
    if (event.event === "ack") {
      handlers.onAck?.((event.data ?? {}) as Record<string, unknown>);
      return;
    }

    if (event.event === "options") {
      stagedOptions = (event.data?.action_options as ActionOptionV2[]) ?? [];
      return;
    }

    if (event.event === "primary") {
      handlers.onPrimary?.(String(event.data?.text ?? ""));
      return;
    }

    if (event.event === "delta") {
      const raw = String(event.data?.text ?? "");
      const safe = sanitizeStreamingDelta(raw, sanitizeState);
      if (safe) handlers.onDelta?.(safe);
      return;
    }

    if (event.event === "progress") {
      handlers.onProgress?.((event.data ?? {}) as Record<string, unknown>);
      return;
    }

    if (event.event === "done") {
      const narrative = (event.data?.narrative as { primary?: string; detail?: string }) ?? {};
      donePayload = {
        turn_id: String(event.data?.turn_id ?? ""),
        turn_index: Number(event.data?.turn_index ?? 0),
        assistant_text: String(narrative.primary ?? ""),
        narrative: {
          primary: String(narrative.primary ?? ""),
          detail: typeof narrative.detail === "string" ? narrative.detail : undefined,
        },
        action_options:
          ((event.data?.action_options as ActionOptionV2[]) ?? stagedOptions ?? []).filter(
            (item) => typeof item?.id === "string" && typeof item?.send_text === "string",
          ),
        battle_summary: (event.data?.battle_summary as Record<string, unknown>) ?? null,
        state_snapshot: (event.data?.state_snapshot as Record<string, unknown>) ?? {},
        provider_latency_ms: Number(event.data?.provider_latency_ms ?? 0),
        token_usage: (event.data?.usage as Record<string, number>) ?? {},
        kernel_delta_summary: (event.data?.kernel_delta_summary as Record<string, unknown>) ?? {},
        time_class_applied: event.data?.time_class_applied
          ? String(event.data.time_class_applied)
          : null,
        timings: (event.data?.timings as GameTurnResponse["timings"]) ?? undefined,
        injection_stats:
          (event.data?.injection_stats as GameTurnResponse["injection_stats"]) ?? undefined,
        pace: (event.data?.pace as GameTurnResponse["pace"]) ?? "balanced",
        quality_mode:
          (event.data?.quality_mode as GameTurnResponse["quality_mode"]) ?? "normal",
      };
      handlers.onDone?.(donePayload);
      return;
    }

    if (event.event === "error") {
      throw new Error(
        `${String(event.data?.message ?? "stream error")} (code=${String(event.data?.code ?? "stream_error")})`,
      );
    }
  });

  if (!donePayload) {
    throw new Error("stream ended without done event");
  }
  return donePayload;
}
