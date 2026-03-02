import { Role } from "@/lib/schemas/types";

export function canAccessOps(role: Role | null): boolean {
  return role === "admin" || role === "operator";
}

export function canConfirmEvents(role: Role | null): boolean {
  return role === "admin" || role === "operator";
}

export function canUseDebugPanel(role: Role | null): boolean {
  return role === "admin" || role === "operator";
}

export function isReadOnly(role: Role | null): boolean {
  return role === "viewer";
}
