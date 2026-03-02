"use client";

import { PropsWithChildren } from "react";
import AppShell from "@/components/layout/AppShell";
import RequireAuth from "@/components/layout/RequireAuth";

export default function DashboardLayout({ children }: PropsWithChildren) {
  return (
    <RequireAuth>
      <AppShell>{children}</AppShell>
    </RequireAuth>
  );
}
