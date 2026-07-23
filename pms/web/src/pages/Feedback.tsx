// 绩效反馈页（PRD 3.4.8）
// 两种入口：
//   - 上级/HR：从下属列表点进来 → 写面谈记录
//   - 员工：从首页 → 查看上级对自己的反馈 → 确认/有异议
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  Modal,
  Space,
  Tag,
  message,
} from "antd";
import { api, formatError } from "@/services/api";
import { useAuth } from "@/stores/auth";


interface FeedbackData {
  id: number;
  cycle_id: number;
  user_id: number;
  interviewer_name: string;
  strengths: string;
  improvements: string;
  next_goals: string;
  confirm_status: string;
  dispute_comment: string | null;
  created_at: string;
  confirmed_at: string | null;
}

const STATUS_LABEL: Record<string, string> = {
  pending: "待确认",
  confirmed: "已确认",
  disputed: "有异议",
};
const STATUS_COLOR: Record<string, string> = {
  pending: "orange",
  confirmed: "green",
  disputed: "red",
};

export default function Feedback() {
  const { cycleId, userId } = useParams();
  const user = useAuth((s) => s.user)!;
  const [fb, setFb] = useState<FeedbackData | null | undefined>(undefined);
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [disputing, setDisputing] = useState(false);
  const [disputeComment, setDisputeComment] = useState("");

  // 目标用户：如果 URL 有 userId 就是看/写别人的；没有就是看自己的
  const targetId = userId ? Number(userId) : user.id;
  const isSelf = targetId === user.id;
  const canWrite = !isSelf; // 上级/HR 能写；员工只能看自己的

  async function load() {
    try {
      const r = await api.get(`/v1/feedback/cycles/${cycleId}/users/${targetId}`);
      setFb(r.data);
      if (r.data) {
        form.setFieldsValue(r.data);
      }
    } catch {
      setFb(null);
    }
  }
  useEffect(() => { load(); }, [cycleId, targetId]);

  async function onSubmitFeedback() {
    const v = await form.validateFields();
    setSaving(true);
    try {
      const r = await api.post(`/v1/feedback/cycles/${cycleId}/users/${targetId}`, v);
      message.success("面谈记录已保存");
      setFb(r.data);
    } catch (e) {
      message.error(formatError(e, "保存失败"));
    } finally { setSaving(false); }
  }

  async function onConfirm() {
    try {
      await api.post(`/v1/feedback/cycles/${cycleId}/confirm`, { action: "confirmed" });
      message.success("已确认收到");
      await load();
    } catch (e) { message.error(formatError(e, "操作失败")); }
  }

  async function onDispute() {
    if (!disputeComment.trim()) { message.error("请填写异议原因"); return; }
    try {
      await api.post(`/v1/feedback/cycles/${cycleId}/confirm`, {
        action: "disputed",
        comment: disputeComment,
      });
      message.success("异议已提交");
      setDisputing(false);
      await load();
    } catch (e) { message.error(formatError(e, "操作失败")); }
  }

  if (fb === undefined) return null;

  return (
    <Space direction="vertical" size="large" style={{ width: "100%", maxWidth: 800 }}>
      <Card title="绩效反馈面谈">
        {fb && (
          <Descriptions column={2} size="small" style={{ marginBottom: 16 }}>
            <Descriptions.Item label="面谈人">{fb.interviewer_name}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={STATUS_COLOR[fb.confirm_status]}>{STATUS_LABEL[fb.confirm_status]}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">{fb.created_at}</Descriptions.Item>
            {fb.confirmed_at && <Descriptions.Item label="确认时间">{fb.confirmed_at}</Descriptions.Item>}
          </Descriptions>
        )}

        {/* 上级写面谈记录 */}
        {canWrite && (
          <>
            {!fb && <Alert type="info" showIcon message="尚未填写面谈记录" style={{ marginBottom: 16 }} />}
            <Form form={form} layout="vertical" onFinish={onSubmitFeedback}>
              <Form.Item name="strengths" label="员工优势" rules={[{ required: true }]}>
                <Input.TextArea rows={3} placeholder="本周期的亮点和突出能力" />
              </Form.Item>
              <Form.Item name="improvements" label="待改进项" rules={[{ required: true }]}>
                <Input.TextArea rows={3} placeholder="具体需要改善的方面" />
              </Form.Item>
              <Form.Item name="next_goals" label="下阶段目标/期望" rules={[{ required: true }]}>
                <Input.TextArea rows={3} placeholder="对下一周期的期望和方向" />
              </Form.Item>
              <Form.Item>
                <Button type="primary" htmlType="submit" loading={saving}>
                  {fb ? "更新面谈记录" : "提交面谈记录"}
                </Button>
              </Form.Item>
            </Form>
          </>
        )}

        {/* 员工查看 + 确认 */}
        {isSelf && fb && (
          <>
            <Card type="inner" title="面谈内容">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="员工优势">{fb.strengths}</Descriptions.Item>
                <Descriptions.Item label="待改进项">{fb.improvements}</Descriptions.Item>
                <Descriptions.Item label="下阶段目标">{fb.next_goals}</Descriptions.Item>
              </Descriptions>
            </Card>

            {fb.confirm_status === "pending" && (
              <Space style={{ marginTop: 16 }}>
                <Button type="primary" onClick={onConfirm}>确认收到</Button>
                <Button danger onClick={() => setDisputing(true)}>有异议</Button>
              </Space>
            )}
            {fb.confirm_status === "disputed" && fb.dispute_comment && (
              <Alert type="error" style={{ marginTop: 16 }} message={`你的异议：${fb.dispute_comment}`} />
            )}
          </>
        )}

        {isSelf && !fb && (
          <Alert type="info" showIcon message="上级尚未填写面谈记录，请耐心等待" />
        )}
      </Card>

      <Modal
        open={disputing}
        title="填写异议"
        onOk={onDispute}
        onCancel={() => setDisputing(false)}
      >
        <Input.TextArea
          rows={4}
          value={disputeComment}
          onChange={(e) => setDisputeComment(e.target.value)}
          placeholder="请说明你对绩效结果或面谈内容的异议"
        />
      </Modal>
    </Space>
  );
}
