"use client";

import { useState } from "react";
import { Button, Input, Select, Space, Table, Tag } from "antd";
import { useQuery } from "@tanstack/react-query";
import { listCanonMoves } from "@/lib/api/endpoints";
import { CanonMoveItem } from "@/lib/schemas/types";

type Props = {
  onCopy: (text: string) => void;
};

export default function MoveSearchPanel({ onCopy }: Props) {
  const [keyword, setKeyword] = useState("");
  const [gen, setGen] = useState<number | undefined>(9);
  const query = useQuery({
    queryKey: ["canon-moves", keyword, gen],
    queryFn: () => listCanonMoves({ q: keyword, generation: gen }),
  });

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      <Space wrap>
        <Input
          placeholder="招式名 / slug"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          style={{ width: 260 }}
        />
        <Select
          allowClear
          style={{ width: 120 }}
          value={gen}
          onChange={setGen}
          options={Array.from({ length: 9 }).map((_, i) => ({ value: i + 1, label: `Gen ${i + 1}` }))}
        />
        <Button onClick={() => query.refetch()} loading={query.isFetching}>
          查询
        </Button>
      </Space>
      <Table<CanonMoveItem>
        size="small"
        loading={query.isLoading}
        rowKey="id"
        dataSource={query.data ?? []}
        pagination={{ pageSize: 8 }}
        columns={[
          { title: "名称", dataIndex: "name_zh", width: 160 },
          { title: "slug", dataIndex: "slug_id", width: 180 },
          {
            title: "属性/分类",
            render: (_, item) => (
              <Space>
                <Tag>{item.type}</Tag>
                <Tag color="purple">{item.category}</Tag>
              </Space>
            ),
          },
          {
            title: "威力/命中",
            render: (_, item) => `${item.power ?? "-"} / ${item.accuracy ?? "-"}`,
            width: 120,
          },
          {
            title: "操作",
            render: (_, record) => (
              <Button
                type="link"
                onClick={() =>
                  onCopy(
                    `${record.name_zh}(${record.slug_id}) ${record.type}/${record.category} 威力:${record.power ?? "-"}`,
                  )
                }
              >
                复制到调试输入
              </Button>
            ),
          },
        ]}
      />
    </Space>
  );
}
