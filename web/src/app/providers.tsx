"use client";

import "@ant-design/v5-patch-for-react-19";
import { ReactNode, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App as AntApp, ConfigProvider } from "antd";

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
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: "#0d5df5",
          borderRadius: 10,
        },
      }}
    >
      <AntApp>
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      </AntApp>
    </ConfigProvider>
  );
}
