"use client";

import { useQuery } from "@tanstack/react-query";
import { Button, Card, Col, Row, Space, Statistic, Tag, Typography } from "antd";
import { getHealth, getMetricsSummary, getReady, getRecentLogs } from "@/lib/api/endpoints";
import { canAccessOps } from "@/lib/auth/guards";
import { getRole } from "@/lib/auth/token";

export default function OpsPage() {
  const role = getRole();
  const allowed = canAccessOps(role);

  const summaryQuery = useQuery({
    queryKey: ["metrics-summary"],
    queryFn: getMetricsSummary,
    enabled: allowed,
    refetchInterval: 5000,
  });
  const logsQuery = useQuery({
    queryKey: ["recent-logs"],
    queryFn: () => getRecentLogs(200),
    enabled: allowed,
    refetchInterval: 5000,
  });
  const healthQuery = useQuery({ queryKey: ["healthz"], queryFn: getHealth, refetchInterval: 5000 });
  const readyQuery = useQuery({ queryKey: ["readyz"], queryFn: getReady, refetchInterval: 5000 });

  if (!allowed) {
    return <Typography.Text>当前角色无权限访问 Ops 面板。</Typography.Text>;
  }

  const summary = summaryQuery.data;

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      <Space>
        <Tag color={healthQuery.data?.status === "ok" ? "green" : "red"}>
          healthz: {healthQuery.data?.status ?? "unknown"}
        </Tag>
        <Tag color={readyQuery.data?.status === "ready" ? "green" : "orange"}>
          readyz: {readyQuery.data?.status ?? "unknown"}
        </Tag>
      </Space>

      <Row gutter={[16, 16]}>
        <Col span={8}>
          <Card>
            <Statistic title="请求总量" value={summary?.requests_total ?? 0} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="5xx 总量" value={summary?.requests_5xx_total ?? 0} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="Provider 平均延迟(ms)"
              value={summary?.provider_latency_ms_avg ?? 0}
              precision={2}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="Vector 命中" value={summary?.vector_hits_total ?? 0} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="Timeline 命中" value={summary?.timeline_hits_total ?? 0} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="Turn 总数" value={summary?.turns_created_total ?? 0} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="冲突总数" value={summary?.conflicts_total ?? 0} />
          </Card>
        </Col>
      </Row>

      <Card
        title="Recent Logs"
        extra={
          <Button size="small" onClick={() => logsQuery.refetch()} loading={logsQuery.isFetching}>
            刷新日志
          </Button>
        }
      >
        <Typography.Paragraph type="secondary" style={{ marginBottom: 8 }}>
          {logsQuery.data?.path ?? "-"}
        </Typography.Paragraph>
        <pre
          style={{
            margin: 0,
            whiteSpace: "pre-wrap",
            maxHeight: 320,
            overflow: "auto",
            fontSize: 12,
          }}
        >
          {(logsQuery.data?.lines ?? []).join("\n")}
        </pre>
      </Card>
    </Space>
  );
}
