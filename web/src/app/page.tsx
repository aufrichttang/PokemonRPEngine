"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/adventure");
  }, [router]);

  return (
    <div className="grid min-h-screen place-items-center">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-[#4da3ff]/30 border-t-[#4da3ff]" />
    </div>
  );
}
