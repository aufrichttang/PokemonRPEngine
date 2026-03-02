"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Spin } from "antd";
import { getToken } from "@/lib/auth/token";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace(getToken() ? "/sessions" : "/login");
  }, [router]);

  return (
    <div style={{ display: "grid", placeItems: "center", minHeight: "100vh" }}>
      <Spin size="large" />
    </div>
  );
}
