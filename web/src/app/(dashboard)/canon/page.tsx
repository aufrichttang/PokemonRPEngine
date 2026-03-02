"use client";

import { useState } from "react";
import { App, Card, Input, Space, Tabs, Typography } from "antd";
import MoveSearchPanel from "@/components/canon/MoveSearchPanel";
import PokemonSearchPanel from "@/components/canon/PokemonSearchPanel";
import TypeChartPanel from "@/components/canon/TypeChartPanel";

export default function CanonPage() {
  const { message } = App.useApp();
  const [scratch, setScratch] = useState("");

  const copyToScratch = (text: string) => {
    setScratch((prev) => (prev ? `${prev}\n${text}` : text));
    message.success("已写入调试草稿");
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      <Typography.Title level={4} style={{ margin: 0 }}>
        Canon 数据工作台
      </Typography.Title>
      <Typography.Paragraph type="secondary">
        用于检索宝可梦设定并复制到调试输入，避免剧情调试时引用错误事实。
      </Typography.Paragraph>
      <Tabs
        defaultActiveKey="pokemon"
        items={[
          { key: "pokemon", label: "Pokemon", children: <PokemonSearchPanel onCopy={copyToScratch} /> },
          { key: "moves", label: "Moves", children: <MoveSearchPanel onCopy={copyToScratch} /> },
          { key: "type-chart", label: "Type Chart", children: <TypeChartPanel /> },
        ]}
      />
      <Card title="调试草稿板" size="small">
        <Input.TextArea
          rows={6}
          value={scratch}
          onChange={(e) => setScratch(e.target.value)}
          placeholder="这里会累积你复制的 Canon 事实，可粘贴到会话调试输入。"
        />
      </Card>
    </Space>
  );
}
