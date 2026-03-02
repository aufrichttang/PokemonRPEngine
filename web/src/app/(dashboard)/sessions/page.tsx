"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  App,
  Button,
  Card,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
} from "antd";
import { apiBaseUrl } from "@/lib/api/client";
import { createSession, deleteSession, listSessions } from "@/lib/api/endpoints";
import { getRole, getToken } from "@/lib/auth/token";
import { SessionItem } from "@/lib/schemas/types";

type CreateSessionForm = {
  title: string;
  canon_gen: number;
  canon_game: string;
  custom_lore_enabled: boolean;
};

export default function SessionsPage() {
  const [open, setOpen] = useState(false);
  const [keyword, setKeyword] = useState("");
  const { message } = App.useApp();
  const role = getRole();
  const queryClient = useQueryClient();
  const sessionsQuery = useQuery({
    queryKey: ["sessions"],
    queryFn: () => listSessions(1, 100),
    staleTime: 15_000,
    refetchOnWindowFocus: false,
  });

  const createMutation = useMutation({
    mutationFn: (payload: CreateSessionForm) =>
      createSession({
        title: payload.title,
        canon_gen: payload.canon_gen,
        canon_game: payload.canon_game || null,
        custom_lore_enabled: payload.custom_lore_enabled,
      }),
    onSuccess: () => {
      message.success("会话已创建");
      setOpen(false);
      void queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
    onError: () => message.error("创建失败"),
  });

  const deleteMutation = useMutation({
    mutationFn: (sessionId: string) => deleteSession(sessionId),
    onSuccess: () => {
      message.success("会话已删除");
      void queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
    onError: () => message.error("删除失败"),
  });

  const filtered = useMemo(() => {
    const rows = sessionsQuery.data ?? [];
    if (!keyword.trim()) return rows;
    return rows.filter((row) => row.title.toLowerCase().includes(keyword.toLowerCase()));
  }, [sessionsQuery.data, keyword]);

  const exportSession = async (sessionId: string, fmt: "json" | "markdown") => {
    const token = getToken();
    if (!token) return;
    const response = await fetch(`${apiBaseUrl()}/v1/sessions/${sessionId}/export?fmt=${fmt}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.text();
    const blob = new Blob([data], { type: fmt === "json" ? "application/json" : "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `session-${sessionId}.${fmt === "json" ? "json" : "md"}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card>
        <Space style={{ width: "100%", justifyContent: "space-between" }} wrap>
          <Space>
            <Typography.Title level={4} style={{ margin: 0 }}>
              会话管理
            </Typography.Title>
            <Tag color="blue">{role ?? "unknown"}</Tag>
          </Space>
          <Space>
            <Input
              placeholder="按标题过滤"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              style={{ width: 220 }}
            />
            <Button onClick={() => sessionsQuery.refetch()} loading={sessionsQuery.isFetching}>
              刷新
            </Button>
            <Button type="primary" onClick={() => setOpen(true)}>
              新建会话
            </Button>
          </Space>
        </Space>
      </Card>

      <Table<SessionItem>
        rowKey="id"
        loading={sessionsQuery.isLoading}
        dataSource={filtered}
        pagination={{ pageSize: 12 }}
        columns={[
          { title: "标题", dataIndex: "title" },
          { title: "更新时间", dataIndex: "updated_at", width: 220 },
          {
            title: "Canon",
            width: 160,
            render: (_, row) => `Gen ${row.canon_gen} / ${row.canon_game ?? "-"}`,
          },
          {
            title: "操作",
            width: 280,
            render: (_, row) => (
              <Space size="small" wrap>
                <Link href={`/sessions/${row.id}`}>进入</Link>
                <Button size="small" onClick={() => void exportSession(row.id, "json")}>
                  导出JSON
                </Button>
                <Button size="small" onClick={() => void exportSession(row.id, "markdown")}>
                  导出MD
                </Button>
                <Button
                  size="small"
                  danger
                  loading={deleteMutation.isPending}
                  onClick={() => deleteMutation.mutate(row.id)}
                >
                  删除
                </Button>
              </Space>
            ),
          },
        ]}
      />

      <Modal title="新建会话" open={open} onCancel={() => setOpen(false)} footer={null}>
        <Form<CreateSessionForm>
          layout="vertical"
          initialValues={{ title: "新会话", canon_gen: 9, canon_game: "sv", custom_lore_enabled: false }}
          onFinish={(values) => createMutation.mutate(values)}
        >
          <Form.Item name="title" label="标题" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="canon_gen" label="世代" rules={[{ required: true }]}>
            <Select options={Array.from({ length: 9 }).map((_, i) => ({ value: i + 1, label: `Gen ${i + 1}` }))} />
          </Form.Item>
          <Form.Item name="canon_game" label="游戏版本">
            <Input placeholder="sv / oras / ... " />
          </Form.Item>
          <Form.Item name="custom_lore_enabled" label="自定义世界观" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Button htmlType="submit" type="primary" block loading={createMutation.isPending}>
            创建
          </Button>
        </Form>
      </Modal>
    </Space>
  );
}
