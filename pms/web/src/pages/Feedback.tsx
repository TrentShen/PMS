// 绩效反馈页（PRD 3.4.8）
// 两种入口：
//   - 上级/HR：从下属列表点进来 → 写面谈记录
//   - 员工：从首页 → 查看上级对自己的反馈 → 确认/有异议
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Spin,
  message,
} from "antd";
import { api, formatError } from "@/services/api";
import { useAuth } from "@/stores/auth";
import { hasAnyRole } from "@/components/RequireRole";
import { ROLE } from "@/App";
import BottomActions from "@/components/ui/BottomActions";
import StatusTag from "@/components/ui/StatusTag";
import type { StatusType } from "@/components/ui/StatusTag";


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
const STATUS_TAG_TYPE: Record<string, StatusType> = {
  pending: "warning",
  confirmed: "success",
  disputed: "danger",
};

export default function Feedback() {
  const { cycleId, userId } = useParams();
  const user = useAuth((s) => s.user)!;
  const [fb, setFb] = useState<FeedbackData | null | undefined>(undefined);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [disputing, setDisputing] = useState(false);
  const [disputeComment, setDisputeComment] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [disputeSaving, setDisputeSaving] = useState(false);
  // 竞态防护：快速切换被反馈人时，旧请求的响应不得写入新目标的表单
  const loadSeq = useRef(0);

  // 目标用户：如果 URL 有 userId 就是看/写别人的；没有就是看自己的
  const targetId = userId ? Number(userId) : user.id;
  const isSelf = targetId === user.id;
  // 上级角色/HR 才能写别人的面谈记录；员工只能看自己的
  const canWrite = !isSelf && (hasAnyRole(user.role, [...ROLE.LEADER]) || user.has_hr_permission);

  async function load() {
    setLoadError(null);
    const seq = ++loadSeq.current;
    try {
      const r = await api.get(`/v1/feedback/cycles/${cycleId}/users/${targetId}`);
      if (seq !== loadSeq.current) return; // 已有更新的请求发出，丢弃旧响应
      setFb(r.data);
      if (r.data) {
        form.setFieldsValue(r.data);
      }
    } catch (e) {
      if (seq !== loadSeq.current) return;
      // 请求失败（403/500 等）不能伪装成"暂无记录"，要明确报错
      const msg = formatError(e, "加载反馈记录失败");
      setFb(null);
      setLoadError(msg);
      message.error(msg);
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
    setConfirming(true);
    try {
      await api.post(`/v1/feedback/cycles/${cycleId}/confirm`, { action: "confirmed" });
      message.success("已确认收到");
      await load();
    } catch (e) { message.error(formatError(e, "操作失败")); }
    finally { setConfirming(false); }
  }

  async function onDispute() {
    if (!disputeComment.trim()) { message.error("请填写异议原因"); return; }
    setDisputeSaving(true);
    try {
      await api.post(`/v1/feedback/cycles/${cycleId}/confirm`, {
        action: "disputed",
        comment: disputeComment,
      });
      message.success("异议已提交");
      setDisputing(false);
      await load();
    } catch (e) { message.error(formatError(e, "操作失败")); }
    finally { setDisputeSaving(false); }
  }

  if (fb === undefined) {
    return (
      <div style={{ textAlign: "center", padding: 64 }}>
        <Spin size="large" />
      </div>
    );
  }

  // 上级填面谈记录时长表单用底部固定提交栏（避免移动端键盘遮挡），容器同步腾出空间
  const showBottomActions = !loadError && canWrite;

  return (
    <Space
      direction="vertical"
      size="large"
      style={{ width: "100%", maxWidth: 800 }}
      className={showBottomActions ? "has-bottom-actions" : undefined}
    >
      <Card title="绩效反馈面谈">
        {loadError && (
          <Alert type="error" showIcon message={loadError} style={{ marginBottom: 16 }} />
        )}
        {!loadError && fb && (
          <Descriptions column={2} size="small" style={{ marginBottom: 16 }}>
            <Descriptions.Item label="面谈人">{fb.interviewer_name}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <StatusTag type={STATUS_TAG_TYPE[fb.confirm_status] ?? "default"}>
                {STATUS_LABEL[fb.confirm_status] ?? fb.confirm_status}
              </StatusTag>
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">{fb.created_at}</Descriptions.Item>
            {fb.confirmed_at && <Descriptions.Item label="确认时间">{fb.confirmed_at}</Descriptions.Item>}
          </Descriptions>
        )}

        {/* 上级写面谈记录 */}
        {!loadError && canWrite && (
          <>
            {!fb && <Alert type="info" showIcon message="尚未填写面谈记录" style={{ marginBottom: 16 }} />}
            <Form
              form={form}
              layout="vertical"
              onFinish={onSubmitFeedback}
              onFinishFailed={({ errorFields }) => {
                // 校验失败时定位到第一个错误字段（长表单 + 底部固定栏，错误可能在视口外）
                if (errorFields.length > 0) form.scrollToField(errorFields[0].name);
              }}
            >
              <Form.Item name="strengths" label="员工优势" rules={[{ required: true }]}>
                <Input.TextArea rows={3} placeholder="本周期的亮点和突出能力" />
              </Form.Item>
              <Form.Item name="improvements" label="待改进项" rules={[{ required: true }]}>
                <Input.TextArea rows={3} placeholder="具体需要改善的方面" />
              </Form.Item>
              <Form.Item name="next_goals" label="下阶段目标/期望" rules={[{ required: true }]}>
                <Input.TextArea rows={3} placeholder="对下一周期的期望和方向" />
              </Form.Item>
              <Form.Item style={{ marginBottom: 0 }}>
                <BottomActions>
                  <Button type="primary" htmlType="submit" loading={saving}>
                    {fb ? "更新面谈记录" : "提交面谈记录"}
                  </Button>
                </BottomActions>
              </Form.Item>
            </Form>
          </>
        )}

        {/* 员工查看 + 确认 */}
        {!loadError && isSelf && fb && (
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
                <Popconfirm
                  title="确认收到面谈结果？"
                  description="确认后不可自行撤销"
                  okText="确认收到"
                  cancelText="取消"
                  onConfirm={onConfirm}
                >
                  <Button type="primary" loading={confirming}>确认收到</Button>
                </Popconfirm>
                <Button danger onClick={() => setDisputing(true)}>有异议</Button>
              </Space>
            )}
            {fb.confirm_status === "disputed" && fb.dispute_comment && (
              <Alert type="error" style={{ marginTop: 16 }} message={`你的异议：${fb.dispute_comment}`} />
            )}
          </>
        )}

        {!loadError && isSelf && !fb && (
          <Alert type="info" showIcon message="上级尚未填写面谈记录，请耐心等待" />
        )}
      </Card>

      <Modal
        open={disputing}
        title="填写异议"
        onOk={onDispute}
        confirmLoading={disputeSaving}
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
