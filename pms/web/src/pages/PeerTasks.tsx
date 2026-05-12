// 我的互评任务：列表 + 填评价（被评人不可见自己的互评内容）
import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Empty,
  Form,
  Input,
  InputNumber,
  List,
  Modal,
  Radio,
  Tag,
  message,
} from "antd";
import { api } from "@/services/api";

interface PeerTask {
  id: number;
  cycle_id: number;
  cycle_name: string;
  target_user_id: number;
  target_name: string;
  target_position: string | null;
  status: string; // pending / submitted
  submitted_at: string | null;
}

export default function PeerTasks() {
  const [tasks, setTasks] = useState<PeerTask[]>([]);
  const [editing, setEditing] = useState<PeerTask | null>(null);
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);

  async function load() {
    const r = await api.get<PeerTask[]>(`/v1/peer/my-tasks`);
    setTasks(r.data);
  }
  useEffect(() => {
    load();
  }, []);

  async function onSubmit() {
    if (!editing) return;
    const v = await form.validateFields();
    if (v.value_grade === "jia" && !v.value_example?.trim()) {
      message.error('价值观评为"甲"时必须填写具体事例');
      return;
    }
    setSaving(true);
    try {
      await api.post(`/v1/peer/tasks/${editing.id}/submit`, v);
      message.success("互评已提交");
      setEditing(null);
      form.resetFields();
      await load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "提交失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="我的互评任务">
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="请客观评价同事；被评人无法看到自己收到的评价内容，请安心填写"
      />
      {tasks.length === 0 ? (
        <Empty description="暂无互评任务" />
      ) : (
        <List
          dataSource={tasks}
          renderItem={(t) => (
            <List.Item
              actions={[
                <Button
                  key="do"
                  type={t.status === "pending" ? "primary" : "default"}
                  onClick={() => {
                    setEditing(t);
                    form.resetFields();
                  }}
                >
                  {t.status === "pending" ? "去评价" : "重新提交"}
                </Button>,
              ]}
            >
              <List.Item.Meta
                title={
                  <>
                    {t.target_name}{" "}
                    <Tag color={t.status === "pending" ? "orange" : "green"}>
                      {t.status === "pending" ? "待评价" : "已提交"}
                    </Tag>
                  </>
                }
                description={`${t.target_position ?? ""} · ${t.cycle_name}`}
              />
            </List.Item>
          )}
        />
      )}

      <Modal
        open={!!editing}
        title={editing ? `评价 ${editing.target_name}` : ""}
        onOk={onSubmit}
        confirmLoading={saving}
        onCancel={() => setEditing(null)}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="perf_score"
            label="业绩评分（1-5，0.25 分段）"
            rules={[{ required: true }]}
          >
            <InputNumber min={1} max={5} step={0.25} style={{ width: 200 }} />
          </Form.Item>
          <Form.Item name="value_grade" label="价值观等级" rules={[{ required: true }]}>
            <Radio.Group>
              <Radio value="jia">甲</Radio>
              <Radio value="yi">乙</Radio>
              <Radio value="bing">丙</Radio>
            </Radio.Group>
          </Form.Item>
          <Form.Item
            shouldUpdate={(a, b) => a.value_grade !== b.value_grade}
            noStyle
          >
            {({ getFieldValue }) =>
              getFieldValue("value_grade") === "jia" ? (
                <Form.Item name="value_example" label='"甲"的具体事例' rules={[{ required: true }]}>
                  <Input.TextArea rows={3} />
                </Form.Item>
              ) : null
            }
          </Form.Item>
          <Form.Item name="comment" label="评语（可选）">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
