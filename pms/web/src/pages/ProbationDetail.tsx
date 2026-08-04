// 试用期详情页
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Button,
  Card,
  Col,
  DatePicker,
  Descriptions,
  Empty,
  Form,
  Input,
  InputNumber,
  message,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Tag,
  Typography,
} from "antd";
import { ArrowLeftOutlined, PlusOutlined, DeleteOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api, formatError } from "@/services/api";
import { useAuth } from "@/stores/auth";
import { hasAnyRole } from "@/components/RequireRole";
import { ROLE } from "@/App";
import { useMobile } from "@/hooks/useMobile";
import BottomActions from "@/components/ui/BottomActions";
import StatusTag, { type StatusType } from "@/components/ui/StatusTag";

// 试用期目标状态（对应后端 ProbationObjectiveStatus：draft/pending_review/approved/locked）
const OBJECTIVE_STATUS_LABEL: Record<string, string> = {
  draft: "草稿",
  pending_review: "待审批",
  approved: "已确认",
  locked: "已锁定",
};
const OBJECTIVE_STATUS_TYPE: Record<string, StatusType> = {
  draft: "default",
  pending_review: "warning",
  approved: "success",
  locked: "info",
};

// 每个计划最多 10 条目标（与后端校验一致）
const MAX_OBJECTIVES = 10;

// 目标卡片字段的小标签样式（与 MyObjectives 对齐，跟随 tokens.css 文本层级色）
const FIELD_LABEL_STYLE: React.CSSProperties = {
  color: "var(--color-text-secondary)",
  fontSize: 13,
  marginBottom: 4,
};


interface ProbationObjective {
  id: number;
  title: string;
  description: string;
  measure_criteria: string;
  weight: number;
  order_num: number;
  status: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  reject_reason: string | null;
}

interface ProbationEvaluation {
  result: string;
  result_text: string;
  comment: string;
  evaluator_name: string;
  evaluated_at: string;
}

interface ProbationPlan {
  id: number;
  user_id: number;
  user_name: string;
  department_name: string | null;
  leader_name: string | null;
  leader_userid: string | null;
  start_date: string;
  end_date: string;
  remaining_days: number;
  status: string;
  status_text: string;
  objectives: ProbationObjective[];
  evaluation: ProbationEvaluation | null;
}

const STATUS_LABEL: Record<string, { text: string; color: string }> = {
  draft: { text: "计划已创建", color: "default" },
  objective_draft: { text: "填写目标中", color: "blue" },
  objective_pending_review: { text: "目标待审批", color: "orange" },
  in_progress: { text: "试用期进行中", color: "processing" },
  pending_evaluation: { text: "临转正，待评估", color: "warning" },
  completed: { text: "已完成", color: "success" },
  extended: { text: "已延期", color: "purple" },
};

const RESULT_OPTIONS = [
  { value: "regular", label: "建议转正" },
  { value: "eliminate", label: "建议淘汰" },
  { value: "pending_other", label: "待定/其他" },
];

export default function ProbationDetail() {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const currentUser = useAuth((s) => s.user)!;
  const isMobile = useMobile();

  const isSelf = currentUser.id === Number(userId);
  const isHr = hasAnyRole(currentUser?.role, [...ROLE.HR]) || currentUser?.has_hr_permission;

  const [plan, setPlan] = useState<ProbationPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // 目标编辑
  const [editingObjectives, setEditingObjectives] = useState<ProbationObjective[]>([]);
  const [objectiveFormChanged, setObjectiveFormChanged] = useState(false);

  // 评估
  const [evalResult, setEvalResult] = useState<string | undefined>(undefined);
  const [evalComment, setEvalComment] = useState("");

  // HR 修改计划
  const [hrModalOpen, setHrModalOpen] = useState(false);
  const [hrStatus, setHrStatus] = useState<string | undefined>(undefined);
  const [hrEndDate, setHrEndDate] = useState<string | undefined>(undefined);
  const [hrNote, setHrNote] = useState("");

  // 驳回目标弹窗
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [rejecting, setRejecting] = useState(false);

  async function load() {
    if (!userId) return;
    setLoading(true);
    try {
      const r = await api.get<ProbationPlan>(`/v1/probation/${userId}`);
      setPlan(r.data);
      setEditingObjectives(r.data.objectives.length ? r.data.objectives : [emptyObjective(0)]);
      if (r.data.evaluation) {
        setEvalResult(r.data.evaluation.result);
        setEvalComment(r.data.evaluation.comment);
      }
    } catch (e) {
      message.error(formatError(e, "加载失败"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [userId]);

  function emptyObjective(idx: number): ProbationObjective {
    return {
      id: 0,
      title: "",
      description: "",
      measure_criteria: "",
      weight: 0,
      order_num: idx,
      status: "draft",
      reviewed_by: null,
      reviewed_at: null,
      reject_reason: null,
    };
  }

  function canEditObjectives() {
    if (!plan) return false;
    if (!(isSelf || isHr)) return false;
    return ["draft", "objective_draft", "objective_pending_review"].includes(plan.status);
  }

  // 审批/评估口径与后端 can_act_as_superior 对齐：HR 或该员工的直属上级；员工本人不能审批/评估自己
  function canActOnPlan(p: ProbationPlan): boolean {
    if (isSelf) return false;
    return Boolean(isHr) || p.leader_userid === currentUser.wecom_userid;
  }

  function canApproveObjectives() {
    if (!plan) return false;
    return canActOnPlan(plan) && plan.status === "objective_pending_review";
  }

  function canEvaluate() {
    if (!plan) return false;
    return canActOnPlan(plan) && ["in_progress", "pending_evaluation", "extended"].includes(plan.status);
  }

  function updateObjective(idx: number, field: keyof ProbationObjective, value: string | number) {
    const next = [...editingObjectives];
    next[idx] = { ...next[idx], [field]: value };
    setEditingObjectives(next);
    setObjectiveFormChanged(true);
  }

  function addObjective() {
    if (editingObjectives.length >= MAX_OBJECTIVES) {
      message.warning(`最多添加 ${MAX_OBJECTIVES} 条目标`);
      return;
    }
    setEditingObjectives([...editingObjectives, emptyObjective(editingObjectives.length)]);
    setObjectiveFormChanged(true);
  }

  function removeObjective(idx: number) {
    const next = editingObjectives.filter((_, i) => i !== idx);
    setEditingObjectives(next.length ? next : [emptyObjective(0)]);
    setObjectiveFormChanged(true);
  }

  async function saveObjectives(submit: boolean) {
    if (!plan || !userId) return;
    const valid = editingObjectives.filter((o) => o.title.trim() && o.description.trim() && o.measure_criteria.trim());
    if (valid.length === 0) {
      message.error("请至少填写一条完整的目标");
      return;
    }
    if (valid.length > 10) {
      message.error("目标不能超过 10 条");
      return;
    }
    setSubmitting(true);
    try {
      await api.post(`/v1/probation/${userId}/objectives`, {
        objectives: valid.map((o, i) => ({
          id: o.id > 0 ? o.id : null,
          title: o.title,
          description: o.description,
          measure_criteria: o.measure_criteria,
          weight: o.weight || 0,
          order_num: i,
        })),
        submit,
      });
      message.success(submit ? "目标已提交" : "目标已保存");
      setObjectiveFormChanged(false);
      load();
    } catch (e) {
      message.error(formatError(e, "保存失败"));
    } finally {
      setSubmitting(false);
    }
  }

  async function approveObjectives() {
    if (!userId) return;
    try {
      await api.post(`/v1/probation/${userId}/objectives/approve`);
      message.success("已批准目标");
      load();
    } catch (e) {
      message.error(formatError(e, "操作失败"));
    }
  }

  async function rejectObjectives(reason: string) {
    if (!userId) return;
    setRejecting(true);
    try {
      await api.post(`/v1/probation/${userId}/objectives/reject`, { reject_reason: reason });
      message.success("已驳回目标");
      setRejectOpen(false);
      setRejectReason("");
      load();
    } catch (e) {
      message.error(formatError(e, "操作失败"));
    } finally {
      setRejecting(false);
    }
  }

  // 驳回必须填写原因（与 Calibration 驳回弹窗同一模式）
  function onConfirmReject() {
    const reason = rejectReason.trim();
    if (!reason) {
      message.warning("驳回必须填写原因");
      return;
    }
    rejectObjectives(reason);
  }

  async function submitEvaluation() {
    if (!userId || !evalResult) return;
    if (!evalComment.trim()) {
      message.error("请填写评估意见");
      return;
    }
    setSubmitting(true);
    try {
      await api.post(`/v1/probation/${userId}/evaluate`, { result: evalResult, comment: evalComment });
      message.success("评估已提交");
      load();
    } catch (e) {
      message.error(formatError(e, "提交失败"));
    } finally {
      setSubmitting(false);
    }
  }

  async function hrUpdatePlan() {
    if (!userId) return;
    if (!hrStatus && !hrEndDate) {
      message.error("请选择要修改的内容");
      return;
    }
    try {
      await api.patch(`/v1/probation/${userId}`, {
        status: hrStatus,
        end_date: hrEndDate,
        extension_note: hrNote,
      });
      message.success("计划已更新");
      setHrModalOpen(false);
      load();
    } catch (e) {
      message.error(formatError(e, "更新失败"));
    }
  }

  if (!plan && !loading) {
    return (
      <Card>
        <Typography.Text type="secondary">试用期计划不存在或无权查看</Typography.Text>
        <div style={{ marginTop: 16 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
            返回
          </Button>
        </div>
      </Card>
    );
  }

  if (!plan) return null;

  const statusCfg = STATUS_LABEL[plan.status] ?? { text: plan.status_text, color: "default" };
  // 编辑态权重合计：等于 100 显示 success，否则 warning（仅提示，不拦截保存）
  const totalWeight = editingObjectives.reduce((s, o) => s + (o.weight || 0), 0);

  return (
    <div className={isMobile && canEditObjectives() ? "has-bottom-actions" : undefined}>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
          返回
        </Button>
        <Typography.Title level={4} style={{ margin: 0 }}>
          试用期详情
        </Typography.Title>
      </Space>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card loading={loading} title="基本信息">
            <Descriptions size="small" column={isMobile ? 1 : 2}>
              <Descriptions.Item label="姓名">{plan.user_name}</Descriptions.Item>
              <Descriptions.Item label="部门">{plan.department_name ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="直属上级">{plan.leader_name ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="试用期起止">
                {plan.start_date} ~ {plan.end_date}
              </Descriptions.Item>
              <Descriptions.Item label="剩余天数">
                {plan.remaining_days < 0 ? `已逾期 ${Math.abs(plan.remaining_days)} 天` : `${plan.remaining_days} 天`}
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={statusCfg.color}>{statusCfg.text}</Tag>
              </Descriptions.Item>
            </Descriptions>
            {isHr && (
              <div style={{ marginTop: 16 }}>
                <Button size="small" onClick={() => setHrModalOpen(true)}>
                  HR 修改计划
                </Button>
              </div>
            )}
          </Card>

          <Card
            loading={loading}
            title="试用期目标"
            style={{ marginTop: 16 }}
            extra={
              canEditObjectives() ? (
                <StatusTag type={totalWeight === 100 ? "success" : "warning"}>权重合计 {totalWeight}%</StatusTag>
              ) : undefined
            }
          >
            {canEditObjectives() ? (
              <>
                {/* 编辑态：每目标一张卡片，风格对齐 MyObjectives */}
                <Space direction="vertical" size="middle" style={{ width: "100%" }}>
                  {editingObjectives.map((o, idx) => (
                    <Card
                      key={idx}
                      size="small"
                      type="inner"
                      title={`目标 ${idx + 1}`}
                      extra={
                        editingObjectives.length > 1 && (
                          <Popconfirm
                            title="确定删除该目标？"
                            okText="删除"
                            cancelText="取消"
                            onConfirm={() => removeObjective(idx)}
                          >
                            <Button type="text" danger size="small" icon={<DeleteOutlined />}>
                              删除
                            </Button>
                          </Popconfirm>
                        )
                      }
                    >
                      <Space direction="vertical" size="middle" style={{ width: "100%" }}>
                        <div>
                          <div style={FIELD_LABEL_STYLE}>目标标题</div>
                          <Input
                            placeholder="例：独立完成 XX 模块的开发与上线"
                            value={o.title}
                            onChange={(e) => updateObjective(idx, "title", e.target.value)}
                          />
                        </div>
                        <div>
                          <div style={FIELD_LABEL_STYLE}>目标描述</div>
                          <Input.TextArea
                            autoSize={{ minRows: 2 }}
                            placeholder="目标的背景、范围与关键交付物"
                            value={o.description}
                            onChange={(e) => updateObjective(idx, "description", e.target.value)}
                          />
                        </div>
                        <div>
                          <div style={FIELD_LABEL_STYLE}>衡量标准</div>
                          <Input.TextArea
                            autoSize={{ minRows: 2 }}
                            placeholder="如何算达成（4分及5分需写出分项考核标准）"
                            value={o.measure_criteria}
                            onChange={(e) => updateObjective(idx, "measure_criteria", e.target.value)}
                          />
                        </div>
                        <div>
                          <div style={FIELD_LABEL_STYLE}>权重</div>
                          <InputNumber
                            min={0}
                            max={100}
                            addonAfter="%"
                            inputMode="decimal"
                            style={{ width: 130 }}
                            placeholder="权重"
                            value={o.weight || undefined}
                            onChange={(v) => updateObjective(idx, "weight", v ?? 0)}
                          />
                        </div>
                      </Space>
                    </Card>
                  ))}
                  <Button
                    type="dashed"
                    block
                    icon={<PlusOutlined />}
                    onClick={addObjective}
                    disabled={editingObjectives.length >= MAX_OBJECTIVES}
                  >
                    添加目标
                  </Button>
                  {editingObjectives.length >= MAX_OBJECTIVES && (
                    <Typography.Text type="secondary">最多添加 {MAX_OBJECTIVES} 条目标</Typography.Text>
                  )}
                </Space>
                {/* 提交=primary，保存草稿=default；移动端这两个按钮移入底部固定栏 */}
                {!isMobile && (
                  <Space style={{ marginTop: 16 }}>
                    <Button loading={submitting} onClick={() => saveObjectives(false)} disabled={!objectiveFormChanged}>
                      保存草稿
                    </Button>
                    <Button type="primary" loading={submitting} onClick={() => saveObjectives(true)}>
                      提交上级审批
                    </Button>
                  </Space>
                )}
              </>
            ) : plan.objectives.length === 0 ? (
              <Empty description={isSelf ? "点击「编辑目标」开始填写" : "员工尚未填写目标"} />
            ) : (
              /* 查看态：目标卡片列表，风格对齐 MyObjectives */
              plan.objectives.map((o, idx) => (
                <Card key={o.id} size="small" style={{ marginBottom: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                    <Typography.Text strong style={{ fontSize: 15 }}>
                      {idx + 1}. {o.title}
                    </Typography.Text>
                    {o.weight > 0 && (
                      <Typography.Text strong style={{ fontSize: 18, color: "var(--color-primary)", flexShrink: 0 }}>
                        {o.weight}%
                      </Typography.Text>
                    )}
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <div style={FIELD_LABEL_STYLE}>目标描述</div>
                    <Typography.Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: 8 }}>
                      {o.description || "-"}
                    </Typography.Paragraph>
                    <div style={FIELD_LABEL_STYLE}>衡量标准</div>
                    <Typography.Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: 8 }}>
                      {o.measure_criteria || "-"}
                    </Typography.Paragraph>
                  </div>
                  <StatusTag type={OBJECTIVE_STATUS_TYPE[o.status] ?? "default"}>
                    {OBJECTIVE_STATUS_LABEL[o.status] ?? o.status}
                  </StatusTag>
                </Card>
              ))
            )}

            {canApproveObjectives() && (
              <Card size="small" title="目标审批" style={{ marginTop: 16 }}>
                <Space wrap>
                  <Button type="primary" onClick={approveObjectives}>
                    批准目标
                  </Button>
                  <Button danger onClick={() => setRejectOpen(true)}>
                    驳回目标
                  </Button>
                </Space>
              </Card>
            )}
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card loading={loading} title="试用期评估">
            {plan.evaluation ? (
              <Descriptions column={1} size="small">
                <Descriptions.Item label="转正建议">
                  {RESULT_OPTIONS.find((o) => o.value === plan.evaluation?.result)?.label ?? plan.evaluation?.result}
                </Descriptions.Item>
                <Descriptions.Item label="评估意见">{plan.evaluation.comment}</Descriptions.Item>
                <Descriptions.Item label="评估人">{plan.evaluation.evaluator_name}</Descriptions.Item>
                <Descriptions.Item label="评估时间">{plan.evaluation.evaluated_at}</Descriptions.Item>
              </Descriptions>
            ) : canEvaluate() ? (
              <Space direction="vertical" style={{ width: "100%" }}>
                <Select
                  placeholder="选择转正建议"
                  style={{ width: "100%" }}
                  options={RESULT_OPTIONS}
                  value={evalResult}
                  onChange={setEvalResult}
                />
                <Input.TextArea
                  placeholder="填写评估意见"
                  rows={4}
                  value={evalComment}
                  onChange={(e) => setEvalComment(e.target.value)}
                />
                <Button type="primary" loading={submitting} onClick={submitEvaluation}>
                  提交评估
                </Button>
              </Space>
            ) : (
              <Typography.Text type="secondary">暂不可评估</Typography.Text>
            )}
          </Card>
        </Col>
      </Row>

      <Modal
        title="HR 修改试用期计划"
        open={hrModalOpen}
        onOk={hrUpdatePlan}
        onCancel={() => setHrModalOpen(false)}
      >
        <Form layout="vertical">
          <Form.Item label="计划状态">
            <Select
              placeholder="选择状态"
              allowClear
              value={hrStatus}
              onChange={setHrStatus}
              options={Object.entries(STATUS_LABEL).map(([k, v]) => ({ value: k, label: v.text }))}
            />
          </Form.Item>
          <Form.Item label="结束日期">
            <DatePicker
              style={{ width: "100%" }}
              value={hrEndDate ? dayjs(hrEndDate) : null}
              onChange={(d) => setHrEndDate(d ? d.format("YYYY-MM-DD") : undefined)}
            />
          </Form.Item>
          <Form.Item label="说明">
            <Input.TextArea rows={3} value={hrNote} onChange={(e) => setHrNote(e.target.value)} placeholder="如延期原因" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 驳回原因弹窗（必填，与 Calibration 驳回弹窗同一模式） */}
      <Modal
        open={rejectOpen}
        title="填写驳回原因"
        onCancel={() => setRejectOpen(false)}
        onOk={onConfirmReject}
        confirmLoading={rejecting}
        okText="确认驳回"
        okButtonProps={{ danger: true }}
        destroyOnClose
      >
        <Input.TextArea
          rows={3}
          value={rejectReason}
          onChange={(e) => setRejectReason(e.target.value)}
          placeholder="必填：请说明驳回原因"
        />
      </Modal>

      {/* 移动端：保存/提交固定在底部操作栏 */}
      {isMobile && canEditObjectives() && (
        <BottomActions>
          <Button loading={submitting} onClick={() => saveObjectives(false)} disabled={!objectiveFormChanged}>
            保存草稿
          </Button>
          <Button type="primary" loading={submitting} onClick={() => saveObjectives(true)}>
            提交上级审批
          </Button>
        </BottomActions>
      )}
    </div>
  );
}
