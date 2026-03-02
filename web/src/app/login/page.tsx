"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { App, Button, Card, Form, Input, Typography } from "antd";
import { login } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/schemas/types";
import { setToken } from "@/lib/auth/token";

type LoginForm = {
  email: string;
  password: string;
};

export default function LoginPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const { message } = App.useApp();

  return (
    <div style={{ display: "grid", placeItems: "center", minHeight: "100vh", padding: 24 }}>
      <Card style={{ width: 420 }}>
        <Typography.Title level={3} style={{ marginTop: 0 }}>
          Pokemon RP 管理台
        </Typography.Title>
        <Typography.Paragraph type="secondary">
          登录后可测试会话、调试记忆注入、排查 Canon 事实冲突。
        </Typography.Paragraph>
        <Form<LoginForm>
          layout="vertical"
          initialValues={{ email: "admin", password: "admin" }}
          onFinish={async (values) => {
            setLoading(true);
            try {
              const result = await login(values.email, values.password);
              setToken(result.access_token);
              router.replace("/sessions");
            } catch (err) {
              const error = err as Partial<ApiError>;
              const code = error.code ?? "unknown_error";
              const msg = error.message ?? (err instanceof Error ? err.message : "Request failed");
              message.error(
                error.trace_id
                  ? `${msg} (code=${code}, trace=${error.trace_id})`
                  : `${msg} (code=${code})`,
              );
            } finally {
              setLoading(false);
            }
          }}
        >
          <Form.Item name="email" label="账号" rules={[{ required: true, min: 1 }]}>
            <Input placeholder="admin 或邮箱" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, min: 1 }]}>
            <Input.Password />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={loading}>
            登录
          </Button>
        </Form>
        <Typography.Paragraph style={{ marginTop: 12, marginBottom: 0 }}>
          还没有账号？<Link href="/register">去注册</Link>
        </Typography.Paragraph>
      </Card>
    </div>
  );
}
