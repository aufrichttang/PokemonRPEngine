"use client";

import { Button, Card, Empty, List, Space, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { getMemoryDebug } from "@/lib/api/endpoints";
import { canUseDebugPanel } from "@/lib/auth/guards";
import { getRole } from "@/lib/auth/token";

type Props = {
  sessionId: string;
};

export default function MemoryDebugPanel({ sessionId }: Props) {
  const role = getRole();
  const allowed = canUseDebugPanel(role);
  const query = useQuery({
    queryKey: ["memory-debug", sessionId],
    queryFn: () => getMemoryDebug(sessionId),
    enabled: allowed,
  });

  if (!allowed) {
    return <Empty description="当前角色无调试权限（仅 admin/operator）" />;
  }

  return (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      <Button onClick={() => query.refetch()} loading={query.isFetching}>
        刷新调试块
      </Button>
      <Card title="Query Plan" size="small">
        <List
          size="small"
          dataSource={query.data?.query_plan ?? []}
          renderItem={(item) => (
            <List.Item>
              <Typography.Text code>{item.type}</Typography.Text>
              <Typography.Text style={{ marginLeft: 8 }}>{item.q}</Typography.Text>
            </List.Item>
          )}
        />
      </Card>
      <Card title="Retrieval Debug" size="small">
        <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>
          {JSON.stringify(query.data?.retrieval ?? {}, null, 2)}
        </pre>
      </Card>
      <Card title="Prompt Injection" size="small">
        <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>
          {query.data?.prompt_injection ?? "(empty)"}
        </pre>
      </Card>
    </Space>
  );
}
