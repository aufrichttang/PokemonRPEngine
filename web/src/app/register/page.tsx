"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { App, Button, Card, Form, Input, Typography } from "antd";
import { register } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/schemas/types";

type RegisterForm = {
  email: string;
  password: string;
  confirm: string;
};

export default function RegisterPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const { message } = App.useApp();

  return (
    <div style={{ display: "grid", placeItems: "center", minHeight: "100vh", padding: 24 }}>
      <Card style={{ width: 460 }}>
        <Typography.Title level={3} style={{ marginTop: 0 }}>
          注册账号
        </Typography.Title>
        <Typography.Paragraph type="secondary">
          注册后可登录管理台。默认管理员账号为 admin/admin。
        </Typography.Paragraph>
        <Form<RegisterForm>
          layout="vertical"
          onFinish={async (values) => {
            setLoading(true);
            try {
              await register(values.email, values.password);
              message.success("注册成功，请登录");
              router.replace("/login");
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
          <Form.Item name="email" label="账号" rules={[{ required: true, min: 1, max: 255 }]}>
            <Input placeholder="如：ash 或 user@example.com" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, min: 1, max: 128 }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item
            name="confirm"
            label="确认密码"
            dependencies={["password"]}
            rules={[
              { required: true, message: "请确认密码" },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue("password") === value) return Promise.resolve();
                  return Promise.reject(new Error("两次输入的密码不一致"));
                },
              }),
            ]}
          >
            <Input.Password />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={loading}>
            注册
          </Button>
        </Form>
        <Typography.Paragraph style={{ marginTop: 12, marginBottom: 0 }}>
          已有账号？<Link href="/login">去登录</Link>
        </Typography.Paragraph>
      </Card>
    </div>
  );
}
