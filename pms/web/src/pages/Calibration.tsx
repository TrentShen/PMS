// 绩效校准页：Leader 改分 + 3-6-1 分布图 + 提交审批 + HR/CEO 审批操作
import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Progress,
  Radio,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { api } from "@/services/api";
import { useAuth } from "@/stores/auth";

interface Cycle { id: number; name: string; status: string }
interface CalItem {
  user_id: number; user_name: string; user_position: string | null; dept_name: string | null;
  initial_perf_score: number | null; initial_perf_level: string | null; initial_value_grade: string | null;
  calibrated_perf_score: number | null; calibrated_perf_level: string | null; calibrated_value_grade: string | null;
  participant_status: string;
}
interface Dist { level: string; label: string; count: number; percent: number; target_percent: string; warning: boolean }

const PERF_LABEL: Record<string, string> = {
  excellent: "优秀", exceed_part: "部分超出", meet: "符合", below_part: "部分不符", below: "不符合",
};
const VALUE_LABEL: Record<string, string> = { jia: "甲", yi: "乙", bing: "丙" };
const APPROVAL_LABEL: Record<string, string> = {
  calibrating: "校准中",
  pending_hr: "等待 HR 审批",
  pending_ceo: "等待 CEO 审批",
  approved: "已批准",
  rejected_by_hr: "HR 已驳回",
  rejected_by_ceo: "CEO 已驳回",
};

export default function Calibration() {
  const user = useAuth((s) => s.user)!;
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [selectedCid, setSelectedCid] = useState<number | null>(null);
  const [items, setItems] = useState<CalItem[]>([]);
  const [distribution, setDistribution] = useState<Dist[]>([]);
  const [approvalStatus, setApprovalStatus] = useState<string>("calibrating");
  const [rejectReason, setRejectReason] = useState<string | null>(null);
  const [editingItem, setEditingItem] = useState<CalItem | null>(null);
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);

  const isHr = user.role === "hrbp" || user.role === "super_admin";
  const isLeader = user.role === "dept_leader";

  useEffect(() => {
    api.get<Cycle[]>("/v1/cycles").then((r) => {
      const inp = r.data.filter((c) => c.status === "in_progress");
      setCycles(inp);
      if (inp.length > 0) setSelectedCid(inp[0].id);
    });
  }, []);

  async function loadView() {
    if (!selectedCid) return;
    try {
      const r = await api.get(`/v1/calibration/cycles/${selectedCid}/view`);
      setItems(r.data.items);
      setDistribution(r.data.distribution);
      setApprovalStatus(r.data.approval_status);
      setRejectReason(r.data.reject_reason);
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "加载失败");
    }
  }
  useEffect(() => { loadView(); }, [selectedCid]);

  async function onCalibrate() {
    if (!editingItem) return;
    const v = await form.validateFields();
    setSaving(true);
    try {
      await api.post(`/v1/calibration/cycles/${selectedCid}/calibrate`, {
        items: [{
          user_id: editingItem.user_id,
          perf_score: v.perf_score,
          value_grade: v.value_grade,
          reason: v.reason,
        }],
      });
      message.success("校准已保存");
      setEditingItem(null);
      form.resetFields();
      await loadView();
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "校准失败");
    } finally { setSaving(false); }
  }

  async function onSubmitCalibration() {
    try {
      await api.post(`/v1/calibration/cycles/${selectedCid}/submit-calibration`);
      message.success("已提交校准，等待 HR 审批");
      await loadView();
    } catch (e: any) { message.error(e?.response?.data?.detail ?? "提交失败"); }
  }

  async function onApproval(action: string) {
    const comment = action === "reject" ? prompt("请填写驳回原因：") : null;
    if (action === "reject" && !comment) { message.warning("驳回必须填写原因"); return; }
    try {
      await api.post(`/v1/calibration/cycles/${selectedCid}/approval`, { action, comment });
      message.success(action === "approve" ? "已批准" : "已驳回");
      await loadView();
    } catch (e: any) { message.error(e?.response?.data?.detail ?? "操作失败"); }
  }

  const canCalibrate = ["calibrating", "rejected_by_hr", "rejected_by_ceo"].includes(approvalStatus);
  const canSubmit = canCalibrate && items.every((i) => i.calibrated_perf_score != null);
  const canApproveHr = isHr && approvalStatus === "pending_hr";
  const canApproveCeo = isHr && approvalStatus === "pending_ceo";

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card
        title="绩效校准"
        extra={
          <Select
            value={selectedCid ?? undefined}
            onChange={setSelectedCid}
            style={{ width: 300 }}
            options={cycles.map((c) => ({ value: c.id, label: c.name }))}
          />
        }
      >
        <Space>
          <Tag color="blue">{APPROVAL_LABEL[approvalStatus] ?? approvalStatus}</Tag>
          {rejectReason && <Typography.Text type="danger">驳回原因：{rejectReason}</Typography.Text>}
        </Space>
      </Card>

      {/* 3-6-1 分布 */}
      <Card title="强制分布（3-6-1）">
        <Space size="large" wrap>
          {distribution.map((d) => (
            <Card key={d.level} type="inner" size="small" style={{ width: 200 }}>
              <Statistic title={`${d.level} 档：${d.label}`} value={`${d.count} 人（${d.percent}%）`} />
              <Typography.Text type="secondary">目标：{d.target_percent}</Typography.Text>
              {d.warning && <Progress percent={d.percent} status="exception" size="small" />}
            </Card>
          ))}
        </Space>
      </Card>

      {/* 参与人列表 */}
      <Card title="校准明细">
        <Table
          rowKey="user_id"
          size="small"
          pagination={false}
          dataSource={items}
          columns={[
            { title: "姓名", dataIndex: "user_name" },
            { title: "部门", dataIndex: "dept_name" },
            { title: "初评分", dataIndex: "initial_perf_score", render: (v) => v?.toFixed(2) ?? "-" },
            { title: "初评等级", dataIndex: "initial_perf_level", render: (v) => PERF_LABEL[v ?? ""] ?? "-" },
            { title: "初评价值观", dataIndex: "initial_value_grade", render: (v) => VALUE_LABEL[v ?? ""] ?? "-" },
            { title: "校准分", dataIndex: "calibrated_perf_score", render: (v) => v != null ? <Tag color="blue">{v.toFixed(2)}</Tag> : "-" },
            { title: "校准等级", dataIndex: "calibrated_perf_level", render: (v) => v ? <Tag>{PERF_LABEL[v]}</Tag> : "-" },
            { title: "校准价值观", dataIndex: "calibrated_value_grade", render: (v) => v ? <Tag>{VALUE_LABEL[v]}</Tag> : "-" },
            {
              title: "操作",
              render: (_, r) =>
                canCalibrate ? (
                  <a onClick={() => { setEditingItem(r); form.setFieldsValue({ perf_score: r.calibrated_perf_score, value_grade: r.calibrated_value_grade, reason: "" }); }}>
                    校准
                  </a>
                ) : null,
            },
          ]}
        />
      </Card>

      {/* 提交 / 审批 按钮 */}
      <Card>
        <Space>
          {(isLeader || isHr) && canCalibrate && (
            <Popconfirm title="确认提交校准结果进入审批？" onConfirm={onSubmitCalibration} disabled={!canSubmit}>
              <Button type="primary" disabled={!canSubmit}>
                提交校准（进入 HR 审批）
              </Button>
            </Popconfirm>
          )}
          {canApproveHr && (
            <>
              <Button type="primary" onClick={() => onApproval("approve")}>HR 批准</Button>
              <Button danger onClick={() => onApproval("reject")}>HR 驳回</Button>
            </>
          )}
          {canApproveCeo && (
            <>
              <Button type="primary" onClick={() => onApproval("approve")}>CEO 批准</Button>
              <Button danger onClick={() => onApproval("reject")}>CEO 驳回</Button>
            </>
          )}
        </Space>
      </Card>

      {/* 校准弹窗 */}
      <Modal
        open={!!editingItem}
        title={editingItem ? `校准：${editingItem.user_name}` : ""}
        onCancel={() => setEditingItem(null)}
        onOk={onCalibrate}
        confirmLoading={saving}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="perf_score" label="调整后业绩分（1-5，0.25 分段）">
            <InputNumber min={1} max={5} step={0.25} style={{ width: 200 }} />
          </Form.Item>
          <Form.Item name="value_grade" label="调整后价值观">
            <Radio.Group>
              <Radio value="jia">甲</Radio>
              <Radio value="yi">乙</Radio>
              <Radio value="bing">丙</Radio>
            </Radio.Group>
          </Form.Item>
          <Form.Item name="reason" label="调整原因（必填）" rules={[{ required: true }]}>
            <Input.TextArea rows={3} placeholder="需说明为什么调整" />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
