"use client";

import { useState } from "react";
import { Button, Input, Select, Space, Table, Tag } from "antd";
import { useQuery } from "@tanstack/react-query";
import { listCanonPokemon } from "@/lib/api/endpoints";
import { CanonPokemonItem } from "@/lib/schemas/types";

type Props = {
  onCopy: (text: string) => void;
};

export default function PokemonSearchPanel({ onCopy }: Props) {
  const [keyword, setKeyword] = useState("");
  const [gen, setGen] = useState<number | undefined>(9);
  const query = useQuery({
    queryKey: ["canon-pokemon", keyword, gen],
    queryFn: () => listCanonPokemon({ q: keyword, generation: gen }),
  });

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      <Space wrap>
        <Input
          placeholder="名称 / slug / 别名"
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
      <Table<CanonPokemonItem>
        size="small"
        loading={query.isLoading}
        rowKey="id"
        dataSource={query.data ?? []}
        pagination={{ pageSize: 8 }}
        columns={[
          { title: "Dex", dataIndex: "dex_no", width: 80 },
          { title: "中文名", dataIndex: "name_zh", width: 120 },
          { title: "英文ID", dataIndex: "slug_id", width: 180 },
          {
            title: "属性",
            dataIndex: "types",
            render: (types: string[]) => types.map((t) => <Tag key={t}>{t}</Tag>),
          },
          {
            title: "操作",
            render: (_, record) => (
              <Button
                type="link"
                onClick={() => onCopy(`${record.name_zh}(${record.slug_id}) 类型: ${record.types.join("/")}`)}
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
