"use client";

import { useMemo, useState } from "react";
import { Button, Select, Space, Table, Tag } from "antd";
import { useQuery } from "@tanstack/react-query";
import { getTypeChart } from "@/lib/api/endpoints";
import { TypeChartItem } from "@/lib/schemas/types";

export default function TypeChartPanel() {
  const [gen, setGen] = useState(9);
  const query = useQuery({
    queryKey: ["type-chart", gen],
    queryFn: () => getTypeChart(gen),
  });

  const rows = useMemo(
    () =>
      (query.data ?? []).map((item: TypeChartItem, idx: number) => ({
        key: `${item.atk_type}-${item.def_type}-${idx}`,
        ...item,
      })),
    [query.data],
  );

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      <Space>
        <Select
          style={{ width: 120 }}
          value={gen}
          onChange={setGen}
          options={Array.from({ length: 9 }).map((_, i) => ({ value: i + 1, label: `Gen ${i + 1}` }))}
        />
        <Button onClick={() => query.refetch()} loading={query.isFetching}>
          刷新克制表
        </Button>
      </Space>
      <Table
        size="small"
        rowKey="key"
        dataSource={rows}
        pagination={{ pageSize: 12 }}
        columns={[
          { title: "攻击属性", dataIndex: "atk_type", width: 140 },
          { title: "防御属性", dataIndex: "def_type", width: 140 },
          {
            title: "倍率",
            dataIndex: "multiplier",
            render: (value: number) => (
              <Tag color={value >= 2 ? "red" : value === 1 ? "default" : value === 0 ? "black" : "blue"}>
                {value}
              </Tag>
            ),
          },
        ]}
      />
    </Space>
  );
}
