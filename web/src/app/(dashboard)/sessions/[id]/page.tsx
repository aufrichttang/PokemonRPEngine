"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Card, Col, Row, Space, Tabs, Typography } from "antd";
import ChatComposer from "@/components/chat/ChatComposer";
import ChatStreamView, { ChatBubble } from "@/components/chat/ChatStreamView";
import ConflictPanel from "@/components/debug/ConflictPanel";
import MemoryDebugPanel from "@/components/debug/MemoryDebugPanel";
import { getSessionDetail, sendMessage, streamMessage } from "@/lib/api/endpoints";

export default function SessionDetailPage() {
  const { message } = App.useApp();
  const params = useParams<{ id: string }>();
  const sessionId = params.id;
  const queryClient = useQueryClient();
  const detailQuery = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => getSessionDetail(sessionId),
    enabled: Boolean(sessionId),
    staleTime: 8_000,
    refetchOnWindowFocus: false,
  });

  const [messages, setMessages] = useState<ChatBubble[]>([]);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    if (!detailQuery.data) return;
    const rows: ChatBubble[] = [];
    detailQuery.data.turns.forEach((turn) => {
      rows.push({
        id: `${turn.id}-u`,
        role: "user",
        text: turn.user_text,
        turnIndex: turn.turn_index,
      });
      rows.push({
        id: `${turn.id}-a`,
        role: "assistant",
        text: turn.assistant_text,
        turnIndex: turn.turn_index,
      });
    });
    setMessages(rows);
  }, [detailQuery.data]);

  const metaText = useMemo(() => {
    if (!detailQuery.data) return "";
    return [
      `Session: ${detailQuery.data.id}`,
      `Title: ${detailQuery.data.title}`,
      `Canon: Gen ${detailQuery.data.canon_gen} / ${detailQuery.data.canon_game ?? "-"}`,
      `Turns: ${detailQuery.data.turns.length}`,
    ].join("\n");
  }, [detailQuery.data]);

  const onSubmit = async (text: string, stream: boolean) => {
    setSending(true);
    const userBubble: ChatBubble = {
      id: `local-user-${Date.now()}`,
      role: "user",
      text,
    };
    setMessages((prev) => [...prev, userBubble]);
    try {
      if (stream) {
        const assistantId = `draft-assistant-${Date.now()}`;
        setMessages((prev) => [...prev, { id: assistantId, role: "assistant", text: "" }]);
        const done = await streamMessage(sessionId, text, (chunk) => {
          setMessages((prev) =>
            prev.map((item) =>
              item.id === assistantId ? { ...item, text: `${item.text}${chunk}` } : item,
            ),
          );
        });
        setMessages((prev) =>
          prev.map((item) =>
            item.id === assistantId ? { ...item, turnIndex: done.turn_index, id: `${done.turn_id}-a` } : item,
          ),
        );
      } else {
        const result = await sendMessage(sessionId, text, false);
        setMessages((prev) => [
          ...prev,
          {
            id: `${result.turn_id}-a`,
            role: "assistant",
            text: result.assistant_text,
            turnIndex: result.turn_index,
          },
        ]);
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["session", sessionId] }),
        queryClient.invalidateQueries({ queryKey: ["memory-debug", sessionId] }),
        queryClient.invalidateQueries({ queryKey: ["timeline", sessionId] }),
      ]);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "发送失败");
    } finally {
      setSending(false);
    }
  };

  return (
    <Row gutter={16}>
      <Col xs={24} lg={15}>
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Card title={detailQuery.data?.title ?? "会话"} loading={detailQuery.isLoading}>
            <ChatStreamView messages={messages} />
          </Card>
          <Card>
            <ChatComposer loading={sending} defaultStream={true} onSubmit={onSubmit} />
          </Card>
        </Space>
      </Col>
      <Col xs={24} lg={9}>
        <Tabs
          defaultActiveKey="debug"
          items={[
            {
              key: "debug",
              label: "记忆调试",
              children: <MemoryDebugPanel sessionId={sessionId} />,
            },
            {
              key: "conflicts",
              label: "冲突与待确认",
              children: <ConflictPanel sessionId={sessionId} />,
            },
            {
              key: "meta",
              label: "会话元数据",
              children: (
                <Card size="small">
                  <Typography.Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}>
                    {metaText}
                  </Typography.Paragraph>
                </Card>
              ),
            },
          ]}
        />
      </Col>
    </Row>
  );
}
