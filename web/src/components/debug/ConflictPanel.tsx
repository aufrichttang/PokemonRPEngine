"use client";

import { useMemo } from "react";
import { App, Button, Empty, List, Space, Tag, Typography } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { confirmTimelineEvent, listTimelineEvents } from "@/lib/api/endpoints";
import { canConfirmEvents } from "@/lib/auth/guards";
import { getRole } from "@/lib/auth/token";

type Props = {
  sessionId: string;
};

export default function ConflictPanel({ sessionId }: Props) {
  const role = getRole();
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const pending = useQuery({
    queryKey: ["timeline", sessionId, "pending"],
    queryFn: () => listTimelineEvents(sessionId, "pending"),
  });
  const conflicts = useQuery({
    queryKey: ["timeline", sessionId, "conflict"],
    queryFn: () => listTimelineEvents(sessionId, "conflict"),
  });

  const confirmMutation = useMutation({
    mutationFn: (eventId: string) => confirmTimelineEvent(sessionId, eventId, "admin confirm"),
    onSuccess: () => {
      message.success("事件已确认");
      void queryClient.invalidateQueries({ queryKey: ["timeline", sessionId] });
    },
    onError: () => {
      message.error("确认失败");
    },
  });

  const merged = useMemo(() => [...(pending.data ?? []), ...(conflicts.data ?? [])], [pending.data, conflicts.data]);

  if (!merged.length && !pending.isLoading && !conflicts.isLoading) {
    return <Empty description="暂无 pending/conflict 事件" />;
  }

  return (
    <List
      bordered
      dataSource={merged}
      renderItem={(item) => (
        <List.Item
          actions={
            canConfirmEvents(role)
              ? [
                  <Button
                    key="confirm"
                    type="link"
                    onClick={() => confirmMutation.mutate(item.id)}
                    loading={confirmMutation.isPending}
                  >
                    确认为事实
                  </Button>,
                ]
              : []
          }
        >
          <Space direction="vertical" size={4} style={{ width: "100%" }}>
            <Space>
              <Tag color={item.canon_level === "conflict" ? "red" : "orange"}>
                {item.canon_level}
              </Tag>
              <Typography.Text type="secondary">{item.created_at}</Typography.Text>
            </Space>
            <Typography.Text>{item.event_text}</Typography.Text>
            {item.location ? <Typography.Text type="secondary">地点: {item.location}</Typography.Text> : null}
          </Space>
        </List.Item>
      )}
    />
  );
}
