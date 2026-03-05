"use client";

import { ReactNode, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";

type Props = {
  children: ReactNode;
};

export default function Providers({ children }: Props) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster
        richColors
        position="top-right"
        expand={false}
        closeButton
        toastOptions={{
          classNames: {
            toast:
              "!border !border-white/10 !bg-[rgba(12,20,45,0.95)] !text-[#e6f0ff] !shadow-[0_20px_40px_rgba(0,0,0,.45)]",
            title: "!text-[#eef5ff]",
            description: "!text-[#9fb4d9]",
          },
        }}
      />
    </QueryClientProvider>
  );
}
