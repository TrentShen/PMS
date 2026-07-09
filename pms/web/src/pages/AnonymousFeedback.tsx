// 匿名主动评价页：任何员工都可以对任意在职同事发起
// 评价内容仅 HR / 部门 Leader 可见，被评人和直属上级都不可见
import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Radio,
  Select,
  message,
} from "antd";
import { api, formatError } from "@/services/api";
import { useAuth } from "@/stores/auth";


interface MockUser {
  id: number;
  wecom_userid: string;
  name: string;
  role: string;
  position: string | null;
}

interface Cycle {
  id: number;
  name: string;
  status: string;
}

export default function AnonymousFeedback() {
  const me = useAuth((s) => s.user)!;
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [users, setUsers] = useState<MockUser[]>([]);
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get<Cycle[]>("/v1/cycles").then((r) => setCycles(r.data.filter((c) => c.status === "in_progress")));
    api.get<MockUser[]>("/v1/users").then((r) => setUsers(r.data));
  }, []);

  async function onSubmit() {
    const v = await form.validateFields();
    if (!v.comment?.trim()) {
      message.error("评语必填");
      return;
    }
    setSaving(true);
    try {
      await api.post(`/v1/cycles/${v.cycle_id}/anonymous-feedback`, {
        target_user_id: v.target_user_id,
        perf_score: v.perf_score || null,
        value_grade: v.value_grade || null,
        comment: v.comment,
      });
      message.success("已提交（匿名）");
      form.resetFields();
    } catch (e) {
      message.error(formatError(e, "提交失败"));
    } finally {
      setSaving(false);
    }
  }

  const targetOptions = users
    .filter((u) => u.wecom_userid !== me.wecom_userid && u.role !== "super_admin")
    .map((u) => ({ value: u.id, label: `${u.name}（${u.position ?? ""}）` }));

  return (
    <Card title="匿名主动评价">
      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 16 }}
        message="提交内容仅 HR / 部门 Leader 可见，被评人和直属上级都看不到；请勿用于人身攻击"
      />
      <Form form={form} layout="vertical" style={{ maxWidth: 600 }}>
        <Form.Item
          name="cycle_id"
          label="周期"
          rules={[{ required: true }]}
          initialValue={cycles[0]?.id}
        >
          <Select options={cycles.map((c) => ({ value: c.id, label: c.name }))} />
        </Form.Item>
        <Form.Item name="target_user_id" label="对谁评价" rules={[{ required: true }]}>
          <Select
            showSearch
            placeholder="选择同事"
            optionFilterProp="label"
            options={targetOptions}
          />
        </Form.Item>
        <Form.Item name="perf_score" label="业绩评分（可选，1-5，0.25 分段）">
          <InputNumber min={1} max={5} step={0.25} style={{ width: 200 }} />
        </Form.Item>
        <Form.Item name="value_grade" label="价值观（可选）">
          <Radio.Group>
            <Radio value="jia">甲</Radio>
            <Radio value="yi">乙</Radio>
            <Radio value="bing">丙</Radio>
          </Radio.Group>
        </Form.Item>
        <Form.Item name="comment" label="评语（必填）" rules={[{ required: true }]}>
          <Input.TextArea rows={5} placeholder="基于事实，陈述具体情况" />
        </Form.Item>
        <Form.Item>
          <Button type="primary" onClick={onSubmit} loading={saving}>
            匿名提交
          </Button>
        </Form.Item>
      </Form>
    </Card>
  );
}
