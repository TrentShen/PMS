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
  Tag,
  message,
} from "antd";
import { api, formatError } from "@/services/api";
import ValueGradeForm from "@/components/ValueGradeForm";
import StatusTag from "@/components/ui/StatusTag";


interface PeerTask {
  id: number;
  cycle_id: number;
  cycle_name: string;
  target_user_id: number;
  target_name: string;
  target_position: string | null;
  status: "pending" | "submitted" | "declined";
  decline_reason: string | null;
  submitted_at: string | null;
}

export default function PeerTasks() {
  const [tasks, setTasks] = useState<PeerTask[]>([]);
  const [editing, setEditing] = useState<PeerTask | null>(null);
  const [declining, setDeclining] = useState<PeerTask | null>(null);
  const [declineReason, setDeclineReason] = useState("");
  const [declineSaving, setDeclineSaving] = useState(false);
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
    setSaving(true);
    try {
      await api.post(`/v1/peer/tasks/${editing.id}/submit`, v);
      message.success("互评已提交");
      setEditing(null);
      form.resetFields();
      await load();
    } catch (e) {
      message.error(formatError(e, "提交失败"));
    } finally {
      setSaving(false);
    }
  }

  async function onDecline() {
    if (!declining) return;
    setDeclineSaving(true);
    try {
      const reason = declineReason.trim();
      await api.post(`/v1/peer/tasks/${declining.id}/decline`, {
        reason: reason === "" ? null : reason,
      });
      message.success("已拒绝该互评任务");
      setDeclining(null);
      setDeclineReason("");
      await load();
    } catch (e) {
      message.error(formatError(e, "拒绝失败"));
    } finally {
      setDeclineSaving(false);
    }
  }

  function statusTag(t: PeerTask) {
    if (t.status === "pending") return <Tag color="orange">待评价</Tag>;
    if (t.status === "submitted") return <Tag color="green">已提交</Tag>;
    return <StatusTag type="default">已拒绝</StatusTag>;
  }

  function actionsOf(t: PeerTask) {
    if (t.status === "declined") return [];
    if (t.status === "submitted") {
      return [
        <Button
          key="do"
          onClick={() => {
            setEditing(t);
            form.resetFields();
          }}
        >
          重新提交
        </Button>,
      ];
    }
    return [
      <Button
        key="do"
        type="primary"
        onClick={() => {
          setEditing(t);
          form.resetFields();
        }}
      >
        去评价
      </Button>,
      <Button
        key="decline"
        onClick={() => {
          setDeclining(t);
          setDeclineReason("");
        }}
      >
        拒绝
      </Button>,
    ];
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
            <List.Item actions={actionsOf(t)}>
              <List.Item.Meta
                title={
                  <>
                    {t.target_name} {statusTag(t)}
                  </>
                }
                description={
                  t.status === "declined" && t.decline_reason
                    ? `${t.target_position ?? ""} · ${t.cycle_name} · 拒绝原因：${t.decline_reason}`
                    : `${t.target_position ?? ""} · ${t.cycle_name}`
                }
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
          <ValueGradeForm />
          <Form.Item name="comment" label="评语（可选）">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={!!declining}
        title={declining ? `拒绝对 ${declining.target_name} 的互评` : ""}
        onOk={onDecline}
        confirmLoading={declineSaving}
        okText="确认拒绝"
        onCancel={() => setDeclining(null)}
        destroyOnClose
      >
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="拒绝后该任务将标记为已拒绝，上级评估流程不再等待"
        />
        <Input.TextArea
          rows={3}
          placeholder="拒绝原因（可选），例如：与该同事合作较少，无法客观评价"
          value={declineReason}
          onChange={(e) => setDeclineReason(e.target.value)}
        />
      </Modal>
    </Card>
  );
}
