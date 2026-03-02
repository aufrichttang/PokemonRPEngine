"use client";

import { PropsWithChildren, useMemo } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Layout, Menu, Tag, Typography } from "antd";
import {
  DashboardOutlined,
  ExperimentOutlined,
  LogoutOutlined,
  MessageOutlined,
  RadarChartOutlined,
} from "@ant-design/icons";
import { canAccessOps } from "@/lib/auth/guards";
import { clearToken, getRole } from "@/lib/auth/token";

const { Header, Content, Sider } = Layout;

export default function AppShell({ children }: PropsWithChildren) {
  const pathname = usePathname();
  const router = useRouter();
  const role = getRole();
  const selectedKey = pathname.startsWith("/sessions")
    ? "/sessions"
    : pathname.startsWith("/canon")
      ? "/canon"
      : pathname.startsWith("/ops")
        ? "/ops"
        : "";

  const items = useMemo(() => {
    const menu = [
      { key: "/sessions", icon: <MessageOutlined />, label: <Link href="/sessions">会话调试</Link> },
      { key: "/canon", icon: <ExperimentOutlined />, label: <Link href="/canon">Canon 数据</Link> },
    ];
    if (canAccessOps(role)) {
      menu.push({
        key: "/ops",
        icon: <DashboardOutlined />,
        label: <Link href="/ops">运行指标</Link>,
      });
    }
    menu.push({
      key: "__logout__",
      icon: <LogoutOutlined />,
      label: <span>退出登录</span>,
    });
    return menu;
  }, [role]);

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider width={230} theme="light" breakpoint="lg" collapsedWidth={0}>
        <div style={{ padding: 20, borderBottom: "1px solid #f0f0f0" }}>
          <Typography.Title level={5} style={{ margin: 0 }}>
            <RadarChartOutlined /> Pokemon RP 管理台
          </Typography.Title>
          <Tag color="blue" style={{ marginTop: 10 }}>
            {role ?? "未登录"}
          </Tag>
        </div>
        <Menu
          mode="inline"
          selectedKeys={selectedKey ? [selectedKey] : []}
          items={items}
          onClick={(item) => {
            if (item.key === "__logout__") {
              clearToken();
              router.replace("/login");
            }
          }}
          style={{ borderInlineEnd: 0, height: "100%" }}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: "#fff",
            borderBottom: "1px solid #f0f0f0",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <Typography.Text strong>测试 / 调试 / 运营</Typography.Text>
          <Typography.Text type="secondary">Pokemon RP Engine</Typography.Text>
        </Header>
        <Content style={{ padding: 20 }}>{children}</Content>
      </Layout>
    </Layout>
  );
}
