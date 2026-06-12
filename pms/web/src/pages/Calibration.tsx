// 绩效校准页：Leader 改分 + 3-6-1 分布图 + 提交审批 + HR/CEO 审批操作
import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Progress,
  Select,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from "antd";
import { api } from "@/services/api";
import { useAuth } from "@/stores/auth";
import ValueGradeForm from "@/components/ValueGradeForm";

interface Cycle { id: number; name: string; status: string }
interface CalItem {
  user_id: number; user_name: string; user_position: string | null; dept_name: string | null;
  initial_perf_score: number | null; initial_perf_level: string | null;
  initial_value_belief: string | null; initial_value_team: string | null; initial_value_growth: string | null;
  calibrated_perf_score: number | null; calibrated_perf_level: string | null;
  calibrated_value_belief: string | null; calibrated_value_team: string | null; calibrated_value_growth: string | null;
  participant_status: string;
}
interface Dist { level: string; label: string; count: number; percent: number; target_percent: string; warning: boolean }
interface MatrixRow { group: string; excellent: number; exceed_part: number; meet: number; below_part: number; below: number; unset: number; total: number }
interface MatrixData { by_dept: MatrixRow[]; by_level: MatrixRow[] }

const PERF_LABEL: Record<string, string> = {
  excellent: "优秀", exceed_part: "部分超出", meet: "符合", below_part: "部分不符", below: "不符合",
};
const MATRIX_LEVELS: { key: keyof Omit<MatrixRow, "group" | "total">; label: string }[] = [
  { key: "excellent", label: "优秀" },
  { key: "exceed_part", label: "部分超出" },
  { key: "meet", label: "符合" },
  { key: "below_part", label: "部分不符" },
  { key: "below", label: "不符合" },
  { key: "unset", label: "未评定" },
];

function MatrixTable({ data }: { data: MatrixRow[] }) {
  // 计算每列最大值，用于颜色归一化
  const maxMap: Record<string, number> = {};
  for (const col of MATRIX_LEVELS) {
    maxMap[col.key] = Math.max(1, ...data.map((d) => d[col.key]));
  }

  const cellStyle = (val: number, max: number): React.CSSProperties => {
    if (val === 0) return { textAlign: "center" };
    const ratio = val / max;
    const lightness = 95 - Math.round(ratio * 45); // 95% -> 50%
    return {
      textAlign: "center",
      backgroundColor: `hsl(210, 90%, ${lightness}%)`,
      fontWeight: ratio > 0.5 ? 600 : 400,
      color: ratio > 0.5 ? "#fff" : "#000",
    };
  };

  return (
    <Table
      size="small"
      pagination={false}
      dataSource={data}
      rowKey="group"
      columns={[
        { title: "分组", dataIndex: "group", fixed: "left", width: 120 },
        ...MATRIX_LEVELS.map((col) => ({
          title: col.label,
          dataIndex: col.key,
          width: 90,
          render: (v: number) => <div style={cellStyle(v, maxMap[col.key])}>{v || "—"}</div>,
        })),
        { title: "合计", dataIndex: "total", width: 80, render: (v: number) => <strong>{v}</strong> },
      ]}
      scroll={{ x: 720 }}
    />
  );
}
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
  const [matrix, setMatrix] = useState<MatrixData | null>(null);
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
      setMatrix(r.data.matrix);
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
          value_belief_grade: v.value_belief_grade,
          value_team_grade: v.value_team_grade,
          value_growth_grade: v.value_growth_grade,
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

      {/* 校准矩阵热力图 */}
      {matrix && (
        <Card title="校准矩阵">
          <Tabs
            items={[
              {
                key: "dept",
                label: "按部门",
                children: <MatrixTable data={matrix.by_dept} />,
              },
              {
                key: "level",
                label: "按职级",
                children: <MatrixTable data={matrix.by_level} />,
              },
            ]}
          />
        </Card>
      )}

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
            { title: "初评价值观", render: (_, r) => (
              <Space>
                <span>信念 {VALUE_LABEL[r.initial_value_belief ?? ""] ?? "-"}</span>
                <span>团队 {VALUE_LABEL[r.initial_value_team ?? ""] ?? "-"}</span>
                <span>成长 {VALUE_LABEL[r.initial_value_growth ?? ""] ?? "-"}</span>
              </Space>
            ) },
            { title: "校准分", dataIndex: "calibrated_perf_score", render: (v) => v != null ? <Tag color="blue">{v.toFixed(2)}</Tag> : "-" },
            { title: "校准等级", dataIndex: "calibrated_perf_level", render: (v) => v ? <Tag>{PERF_LABEL[v]}</Tag> : "-" },
            { title: "校准价值观", render: (_, r) => (
              <Space>
                {r.calibrated_value_belief ? <Tag>信念 {VALUE_LABEL[r.calibrated_value_belief]}</Tag> : "-"}
                {r.calibrated_value_team ? <Tag>团队 {VALUE_LABEL[r.calibrated_value_team]}</Tag> : null}
                {r.calibrated_value_growth ? <Tag>成长 {VALUE_LABEL[r.calibrated_value_growth]}</Tag> : null}
              </Space>
            ) },
            {
              title: "操作",
              render: (_, r) =>
                canCalibrate ? (
                  <a onClick={() => { setEditingItem(r); form.setFieldsValue({ perf_score: r.calibrated_perf_score, value_belief_grade: r.calibrated_value_belief, value_team_grade: r.calibrated_value_team, value_growth_grade: r.calibrated_value_growth, reason: "" }); }}>
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
          <ValueGradeForm prefix="value" />
          <Form.Item name="reason" label="调整原因（必填）" rules={[{ required: true }]}>
            <Input.TextArea rows={3} placeholder="需说明为什么调整" />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
