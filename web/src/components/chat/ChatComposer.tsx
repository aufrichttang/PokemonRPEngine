"use client";

import { Form, Input, Space, Switch, Button } from "antd";

type Props = {
  loading: boolean;
  defaultStream: boolean;
  onSubmit: (text: string, stream: boolean) => Promise<void>;
};

export default function ChatComposer({ loading, defaultStream, onSubmit }: Props) {
  const [form] = Form.useForm<{ text: string; stream: boolean }>();

  return (
    <Form
      form={form}
      layout="vertical"
      initialValues={{ stream: defaultStream }}
      onFinish={async (values) => {
        await onSubmit(values.text, values.stream);
        form.setFieldValue("text", "");
      }}
    >
      <Form.Item name="text" label="发送消息" rules={[{ required: true, message: "请输入消息" }]}>
        <Input.TextArea rows={4} placeholder="输入剧情推进或调试问题..." />
      </Form.Item>
      <Space>
        <Form.Item name="stream" valuePropName="checked" noStyle>
          <Switch checkedChildren="流式" unCheckedChildren="非流式" />
        </Form.Item>
        <Button htmlType="submit" type="primary" loading={loading}>
          发送
        </Button>
      </Space>
    </Form>
  );
}
