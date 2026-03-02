import { clearToken, getToken } from "@/lib/auth/token";
import { ApiError } from "@/lib/schemas/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const REQUEST_TIMEOUT_MS = Number(process.env.NEXT_PUBLIC_API_TIMEOUT_MS ?? "12000");

type RequestOptions = {
  method?: "GET" | "POST" | "DELETE";
  body?: unknown;
  auth?: boolean;
  headers?: Record<string, string>;
};

function toApiError(status: number, payload: unknown): ApiError {
  if (payload && typeof payload === "object") {
    const error = (payload as Record<string, unknown>).error;
    if (error && typeof error === "object") {
      return {
        code: String((error as Record<string, unknown>).code ?? "unknown_error"),
        message: String((error as Record<string, unknown>).message ?? "Request failed"),
        trace_id: (error as Record<string, unknown>).trace_id as string | undefined,
        status,
      };
    }
    const detail = (payload as Record<string, unknown>).detail;
    if (typeof detail === "string") {
      return { code: "http_error", message: detail, status };
    }
  }
  return { code: "http_error", message: `Request failed: ${status}`, status };
}

export async function apiRequest<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(opts.headers ?? {}),
  };
  if (opts.auth !== false) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method: opts.method ?? "GET",
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
      cache: "no-store",
      signal: controller.signal,
    });
  } catch (err) {
    const msg =
      err instanceof DOMException && err.name === "AbortError"
        ? `Request timeout after ${REQUEST_TIMEOUT_MS}ms`
        : err instanceof Error
          ? err.message
          : "Network request failed";
    throw {
      code: "network_error",
      message: `Network error: ${msg}`,
      status: 0,
    } satisfies ApiError;
  } finally {
    clearTimeout(timeout);
  }

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text) as unknown;
    } catch {
      payload = { detail: text };
    }
  }
  if (!response.ok) {
    const error = toApiError(response.status, payload);
    if (response.status === 401) {
      clearToken();
    }
    throw error;
  }
  return payload as T;
}

export function apiBaseUrl(): string {
  return BASE_URL;
}
