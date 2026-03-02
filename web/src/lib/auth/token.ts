import { Role } from "@/lib/schemas/types";

const TOKEN_KEY = "rp_admin_token";
const ROLE_KEY = "rp_admin_role";

function safeDecodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const payload = token.split(".")[1];
    if (!payload) return null;
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const pad = "=".repeat((4 - (normalized.length % 4)) % 4);
    const decoded = atob(normalized + pad);
    return JSON.parse(decoded) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(TOKEN_KEY, token);
  const role = getRoleFromToken(token);
  if (role) sessionStorage.setItem(ROLE_KEY, role);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(ROLE_KEY);
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(TOKEN_KEY);
}

export function getRole(): Role | null {
  if (typeof window === "undefined") return null;
  const value = sessionStorage.getItem(ROLE_KEY);
  if (value === "admin" || value === "operator" || value === "viewer" || value === "user") {
    return value;
  }
  return null;
}

export function getRoleFromToken(token: string): Role | null {
  const payload = safeDecodeJwtPayload(token);
  const role = payload?.role;
  if (role === "admin" || role === "operator" || role === "viewer" || role === "user") {
    return role;
  }
  return null;
}
