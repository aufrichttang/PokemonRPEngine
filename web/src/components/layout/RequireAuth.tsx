"use client";

import { PropsWithChildren, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Spin } from "antd";
import { getToken } from "@/lib/auth/token";

export default function RequireAuth({ children }: PropsWithChildren) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    setReady(true);
  }, [router]);

  if (!ready) {
    return (
      <div style={{ display: "grid", placeItems: "center", minHeight: "50vh" }}>
        <Spin size="large" />
      </div>
    );
  }

  return <>{children}</>;
}
