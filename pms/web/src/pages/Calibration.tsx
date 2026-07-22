// 绩效校准页：Leader 改分 + 3-6-1 分布图 + 提交审批 + HR/CEO 审批操作
import { useEffect, useMemo, useState } from "react";
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
  Select,
  Space,
  Statistic,
  Table,
  Tabs,
  Typography,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { Column } from "@ant-design/charts";
import { api, formatError } from "@/services/api";
import { useAuth } from "@/stores/auth";
import ValueGradeForm from "@/components/ValueGradeForm";
import { useMobile } from "@/hooks/useMobile";
import BottomActions from "@/components/ui/BottomActions";
import ResponsiveShow from "@/components/ui/ResponsiveShow";
import StatusTag, { type StatusType } from "@/components/ui/StatusTag";
import TableCardList, { type CardColumn } from "@/components/ui/TableCardList";


interface Cycle {
  id: number;
  name: string;
  status: string;
  enable_calibration: boolean;
}
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

// 校准弹窗表单值（字段名与后端契约一致，example 字段由 ValueGradeForm 注入）
interface CalibrateFormValues {
  perf_score?: number | null;
  value_belief_grade?: string;
  value_team_grade?: string;
  value_growth_grade?: string;
  value_belief_example?: string;
  value_team_example?: string;
  value_growth_example?: string;
  reason: string;
}

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
  const isMobile = useMobile();
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
    <>
      {isMobile && (
        <Typography.Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
          矩阵较宽，手机端建议横屏查看
        </Typography.Text>
      )}
      <div style={{ overflowX: "auto" }}>
        <Table
          size="small"
          pagination={false}
          dataSource={data}
          rowKey="group"
          columns={[
            { title: "分组", dataIndex: "group", fixed: "left", width: 120 },
            ...MATRIX_LEVELS.map((col) => ({
              title: isMobile ? col.label.slice(0, 2) : col.label,
              dataIndex: col.key,
              width: isMobile ? 64 : 90,
              render: (v: number) => <div style={cellStyle(v, maxMap[col.key])}>{v || "—"}</div>,
            })),
            { title: "合计", dataIndex: "total", width: isMobile ? 60 : 80, render: (v: number) => <strong>{v}</strong> },
          ]}
          scroll={{ x: isMobile ? 520 : 720 }}
          style={{ minWidth: isMobile ? 520 : 720 }}
        />
      </div>
    </>
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
const APPROVAL_TAG_TYPE: Record<string, StatusType> = {
  calibrating: "warning",
  pending_hr: "info",
  pending_ceo: "info",
  approved: "success",
  rejected_by_hr: "danger",
  rejected_by_ceo: "danger",
};
const PARTICIPANT_STATUS_LABEL: Record<string, string> = {
  pending: "待自评",
  self_done: "待上级评估",
  leader_done: "上级已评",
  published: "已公布",
  excluded: "已排除",
};
const PARTICIPANT_STATUS_TYPE: Record<string, StatusType> = {
  pending: "default",
  self_done: "info",
  leader_done: "primary",
  published: "success",
  excluded: "default",
};

// 分数变化：上调绿色（--color-success）、下调红色（--color-danger），配色类定义在 global.css
function ScoreDelta({ initial, calibrated }: { initial: number | null; calibrated: number | null }) {
  if (initial == null || calibrated == null) return null;
  const delta = Math.round((calibrated - initial) * 100) / 100;
  if (delta === 0) return null;
  const up = delta > 0;
  return (
    <span className={up ? "pms-score-change-up" : "pms-score-change-down"} style={{ marginLeft: 6, fontSize: 12 }}>
      {up ? "+" : ""}{delta.toFixed(2)}
    </span>
  );
}

// 分数被调整过的行（审批重点关注对象）用 --color-warning-bg 高亮
function isAdjusted(r: CalItem): boolean {
  return (
    r.initial_perf_score != null &&
    r.calibrated_perf_score != null &&
    r.initial_perf_score !== r.calibrated_perf_score
  );
}

// 价值观三维摘要：优先展示校准值，未校准时回退初评值
function valueSummary(r: CalItem): string {
  const belief = r.calibrated_value_belief ?? r.initial_value_belief;
  const team = r.calibrated_value_team ?? r.initial_value_team;
  const growth = r.calibrated_value_growth ?? r.initial_value_growth;
  return `信念 ${VALUE_LABEL[belief ?? ""] ?? "-"} / 团队 ${VALUE_LABEL[team ?? ""] ?? "-"} / 成长 ${VALUE_LABEL[growth ?? ""] ?? "-"}`;
}

// @ant-design/charts 需要具体色值字符串，运行时从设计令牌读取（fallback 与 tokens.css 保持一致）
function getChartColor(token: string, fallback: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(token).trim();
  return v || fallback;
}

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
  const [form] = Form.useForm<CalibrateFormValues>();
  const [saving, setSaving] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectComment, setRejectComment] = useState("");
  const [approvalSaving, setApprovalSaving] = useState(false);

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
    } catch (e) {
      message.error(formatError(e, "加载失败"));
    }
  }
  useEffect(() => { loadView(); }, [selectedCid]);

  // 分布对比图数据：实际分布（--color-chart-1）vs 目标分布（--color-chart-grid）
  // 目标占比从后端文案（如 "≤30%"/"≈60%"/"≥10%"）中提取数值，仅用于展示
  const chartData = useMemo(() => {
    const rows: { level: string; series: string; percent: number }[] = [];
    for (const d of distribution) {
      const levelLabel = `${d.level} 档`;
      rows.push({ level: levelLabel, series: "实际分布", percent: d.percent });
      const m = d.target_percent.match(/\d+(?:\.\d+)?/);
      if (m) rows.push({ level: levelLabel, series: "目标分布", percent: Number(m[0]) });
    }
    return rows;
  }, [distribution]);

  const chartColors = useMemo(
    () => [
      getChartColor("--color-chart-1", "#3370FF"),
      getChartColor("--color-chart-grid", "#E8E9EB"),
    ],
    [],
  );

  function openEdit(r: CalItem) {
    setEditingItem(r);
    form.setFieldsValue({
      perf_score: r.calibrated_perf_score,
      value_belief_grade: r.calibrated_value_belief ?? undefined,
      value_team_grade: r.calibrated_value_team ?? undefined,
      value_growth_grade: r.calibrated_value_growth ?? undefined,
      reason: "",
    });
  }

  async function onCalibrate() {
    if (!editingItem) return;
    let v: CalibrateFormValues;
    try {
      v = await form.validateFields();
    } catch {
      return; // 校验失败：Form 已展示错误提示，阻止提交
    }
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
    } catch (e) {
      message.error(formatError(e, "校准失败"));
    } finally { setSaving(false); }
  }

  async function onSubmitCalibration() {
    try {
      await api.post(`/v1/calibration/cycles/${selectedCid}/submit-calibration`);
      message.success("已提交校准，等待 HR 审批");
      await loadView();
    } catch (e) { message.error(formatError(e, "提交失败")); }
  }

  async function onApproval(action: "approve" | "reject", comment: string | null) {
    setApprovalSaving(true);
    try {
      await api.post(`/v1/calibration/cycles/${selectedCid}/approval`, { action, comment });
      message.success(action === "approve" ? "已批准" : "已驳回");
      setRejectOpen(false);
      setRejectComment("");
      await loadView();
    } catch (e) { message.error(formatError(e, "操作失败")); }
    finally { setApprovalSaving(false); }
  }

  function onConfirmReject() {
    const comment = rejectComment.trim();
    if (!comment) { message.warning("驳回必须填写原因"); return; }
    onApproval("reject", comment);
  }

  const canCalibrate = ["calibrating", "rejected_by_hr", "rejected_by_ceo"].includes(approvalStatus);
  const canSubmit = canCalibrate && items.every((i) => i.calibrated_perf_score != null);
  const canApproveHr = isHr && approvalStatus === "pending_hr";
  const canApproveCeo = isHr && approvalStatus === "pending_ceo";
  const showBottomActions = ((isLeader || isHr) && canCalibrate) || canApproveHr || canApproveCeo;

  const selectedCycle = cycles.find((c) => c.id === selectedCid) ?? null;
  const calibrationEnabled = selectedCycle?.enable_calibration !== false;

  const detailColumns: ColumnsType<CalItem> = [
    { title: "姓名", dataIndex: "user_name" },
    { title: "部门", dataIndex: "dept_name", render: (v: string | null) => v ?? "-" },
    { title: "初评分", dataIndex: "initial_perf_score", render: (v: number | null) => v?.toFixed(2) ?? "-" },
    { title: "初评等级", dataIndex: "initial_perf_level", render: (v: string | null) => PERF_LABEL[v ?? ""] ?? "-" },
    { title: "初评价值观", render: (_: unknown, r: CalItem) => (
      <Space>
        <span>信念 {VALUE_LABEL[r.initial_value_belief ?? ""] ?? "-"}</span>
        <span>团队 {VALUE_LABEL[r.initial_value_team ?? ""] ?? "-"}</span>
        <span>成长 {VALUE_LABEL[r.initial_value_growth ?? ""] ?? "-"}</span>
      </Space>
    ) },
    { title: "校准分", dataIndex: "calibrated_perf_score", render: (v: number | null, r: CalItem) => (
      v != null ? (
        <>
          <StatusTag type="primary">{v.toFixed(2)}</StatusTag>
          <ScoreDelta initial={r.initial_perf_score} calibrated={v} />
        </>
      ) : "-"
    ) },
    { title: "校准等级", dataIndex: "calibrated_perf_level", render: (v: string | null) => (
      v ? <StatusTag>{PERF_LABEL[v] ?? v}</StatusTag> : "-"
    ) },
    { title: "校准价值观", render: (_: unknown, r: CalItem) => (
      <Space>
        {r.calibrated_value_belief ? <StatusTag>信念 {VALUE_LABEL[r.calibrated_value_belief]}</StatusTag> : "-"}
        {r.calibrated_value_team ? <StatusTag>团队 {VALUE_LABEL[r.calibrated_value_team]}</StatusTag> : null}
        {r.calibrated_value_growth ? <StatusTag>成长 {VALUE_LABEL[r.calibrated_value_growth]}</StatusTag> : null}
      </Space>
    ) },
    { title: "状态", dataIndex: "participant_status", render: (v: string) => (
      <StatusTag type={PARTICIPANT_STATUS_TYPE[v] ?? "default"}>
        {PARTICIPANT_STATUS_LABEL[v] ?? v}
      </StatusTag>
    ) },
    {
      title: "操作",
      render: (_: unknown, r: CalItem) =>
        canCalibrate ? <a onClick={() => openEdit(r)}>校准</a> : null,
    },
  ];

  // 移动端卡片列：姓名、部门、初始评分、校准后评分、价值观、状态
  const cardColumns: CardColumn<CalItem>[] = [
    { title: "姓名", dataIndex: "user_name" },
    { title: "部门", render: (r) => r.dept_name ?? "-" },
    { title: "初始评分", render: (r) => r.initial_perf_score?.toFixed(2) ?? "-" },
    { title: "校准后评分", render: (r) => (
      r.calibrated_perf_score != null ? (
        <span>
          {r.calibrated_perf_score.toFixed(2)}
          <ScoreDelta initial={r.initial_perf_score} calibrated={r.calibrated_perf_score} />
        </span>
      ) : "-"
    ) },
    { title: "价值观", render: (r) => valueSummary(r) },
    { title: "状态", render: (r) => (
      <StatusTag type={PARTICIPANT_STATUS_TYPE[r.participant_status] ?? "default"}>
        {PARTICIPANT_STATUS_LABEL[r.participant_status] ?? r.participant_status}
      </StatusTag>
    ) },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }} className="has-bottom-actions">
      <Card
        title="绩效校准"
        extra={
          <Select
            value={selectedCid ?? undefined}
            onChange={setSelectedCid}
            style={{ width: "100%", maxWidth: 300 }}
            options={cycles.map((c) => ({ value: c.id, label: c.name }))}
          />
        }
      >
        <Space>
          <StatusTag type={APPROVAL_TAG_TYPE[approvalStatus] ?? "default"}>
            {APPROVAL_LABEL[approvalStatus] ?? approvalStatus}
          </StatusTag>
          {rejectReason && <Typography.Text type="danger">驳回原因：{rejectReason}</Typography.Text>}
        </Space>
      </Card>

      {!calibrationEnabled && (
        <Alert type="warning" showIcon message="本周期未开启校准环节" />
      )}

      {/* 3-6-1 分布 */}
      <Card title="强制分布（3-6-1）">
        {chartData.length > 0 && (
          <ResponsiveShow on="desktop">
            <div style={{ marginBottom: 16 }}>
              <Column
                data={chartData}
                xField="level"
                yField="percent"
                colorField="series"
                group
                height={260}
                scale={{ color: { range: chartColors } }}
                axis={{ y: { title: "占比（%）" } }}
              />
            </div>
          </ResponsiveShow>
        )}
        <Space size="large" wrap>
          {distribution.map((d) => (
            <Card key={d.level} type="inner" size="small" style={{ flex: "1 1 160px", minWidth: 160, maxWidth: 220 }}>
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

      {/* 参与人列表：桌面表格 + 移动端卡片 */}
      <Card title="校准明细">
        <div className="pms-responsive-table">
          <Table
            rowKey="user_id"
            size="small"
            pagination={false}
            dataSource={items}
            columns={detailColumns}
            scroll={{ x: 1080 }}
            onRow={(r) => ({ className: isAdjusted(r) ? "pms-calibration-adjusted-row" : "" })}
          />
        </div>
        <TableCardList
          columns={cardColumns}
          dataSource={items}
          rowKey={(r) => r.user_id}
          renderActions={(r) =>
            canCalibrate ? (
              <Button size="small" onClick={() => openEdit(r)}>调整</Button>
            ) : null
          }
        />
      </Card>

      {/* 提交 / 审批 按钮：底部固定操作栏 */}
      {showBottomActions && (
        <BottomActions>
          {(isLeader || isHr) && canCalibrate && (
            <Popconfirm title="确认提交校准结果进入审批？" onConfirm={onSubmitCalibration} disabled={!canSubmit}>
              <Button type="primary" disabled={!canSubmit}>
                提交校准（进入 HR 审批）
              </Button>
            </Popconfirm>
          )}
          {canApproveHr && (
            <>
              <Popconfirm title="确认 HR 批准本次校准结果？" onConfirm={() => onApproval("approve", null)}>
                <Button type="primary" loading={approvalSaving}>HR 批准</Button>
              </Popconfirm>
              <Button danger onClick={() => setRejectOpen(true)}>HR 驳回</Button>
            </>
          )}
          {canApproveCeo && (
            <>
              <Popconfirm title="确认 CEO 批准本次校准结果？" onConfirm={() => onApproval("approve", null)}>
                <Button type="primary" loading={approvalSaving}>CEO 批准</Button>
              </Popconfirm>
              <Button danger onClick={() => setRejectOpen(true)}>CEO 驳回</Button>
            </>
          )}
        </BottomActions>
      )}

      {/* 驳回原因弹窗（必填） */}
      <Modal
        open={rejectOpen}
        title="填写驳回原因"
        onCancel={() => setRejectOpen(false)}
        onOk={onConfirmReject}
        confirmLoading={approvalSaving}
        okText="确认驳回"
        okButtonProps={{ danger: true }}
        destroyOnClose
      >
        <Input.TextArea
          rows={3}
          value={rejectComment}
          onChange={(e) => setRejectComment(e.target.value)}
          placeholder="必填：请说明驳回原因"
        />
      </Modal>

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
          <Form.Item
            name="perf_score"
            label="调整后业绩分（1-5，0.25 分段）"
            rules={[
              {
                validator: (_, value: number | null | undefined) => {
                  if (value == null) return Promise.resolve();
                  if (value < 1 || value > 5 || !Number.isInteger(value * 4)) {
                    return Promise.reject(new Error("业绩分需为 1-5 之间、以 0.25 为步进"));
                  }
                  return Promise.resolve();
                },
              },
            ]}
          >
            <InputNumber min={1} max={5} step={0.25} style={{ width: "100%" }} />
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
