"use client";

import { Card, Space, Tag, Typography } from "antd";

export type ChatBubble = {
  id: string;
  role: "user" | "assistant";
  text: string;
  turnIndex?: number;
};

type Props = {
  messages: ChatBubble[];
};

export default function ChatStreamView({ messages }: Props) {
  return (
    <Space direction="vertical" size={10} style={{ width: "100%" }}>
      {messages.map((msg) => (
        <Card
          key={msg.id}
          size="small"
          style={{
            background: msg.role === "user" ? "#eef6ff" : "#fff",
            borderColor: msg.role === "user" ? "#91caff" : "#e5eaf4",
          }}
        >
          <Space direction="vertical" size={4}>
            <Space>
              <Tag color={msg.role === "user" ? "blue" : "purple"}>{msg.role}</Tag>
              {msg.turnIndex ? <Typography.Text type="secondary">Turn {msg.turnIndex}</Typography.Text> : null}
            </Space>
            <Typography.Paragraph style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}>
              {msg.text}
            </Typography.Paragraph>
          </Space>
        </Card>
      ))}
    </Space>
  );
}
