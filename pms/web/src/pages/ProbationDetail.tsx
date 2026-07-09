// 试用期详情页
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  message,
  Modal,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import { ArrowLeftOutlined, PlusOutlined, DeleteOutlined } from "@ant-design/icons";
import { api, formatError } from "@/services/api";
import { useAuth } from "@/stores/auth";
import { hasAnyRole } from "@/components/RequireRole";
import { ROLE } from "@/App";
import { useMobile } from "@/hooks/useMobile";


interface ProbationObjective {
  id: number;
  title: string;
  description: string;
  measure_criteria: string;
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
  const isLeader = hasAnyRole(currentUser?.role, [...ROLE.LEADER]) || currentUser?.has_subordinates;

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

  function canApproveObjectives() {
    if (!plan) return false;
    if (!(isLeader || isHr)) return false;
    return plan.status === "objective_pending_review";
  }

  function canEvaluate() {
    if (!plan) return false;
    if (!(isLeader || isHr)) return false;
    return ["in_progress", "pending_evaluation", "extended"].includes(plan.status);
  }

  function updateObjective(idx: number, field: keyof ProbationObjective, value: string) {
    const next = [...editingObjectives];
    next[idx] = { ...next[idx], [field]: value };
    setEditingObjectives(next);
    setObjectiveFormChanged(true);
  }

  function addObjective() {
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
    try {
      await api.post(`/v1/probation/${userId}/objectives/reject`, { reject_reason: reason });
      message.success("已驳回目标");
      load();
    } catch (e) {
      message.error(formatError(e, "操作失败"));
    }
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

  return (
    <div>
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

          <Card loading={loading} title="试用期目标" style={{ marginTop: 16 }}>
            {editingObjectives.map((o, idx) => (
              <div key={idx} style={{ marginBottom: 16, padding: 12, border: "1px solid #f0f0f0", borderRadius: 8 }}>
                <Space direction="vertical" style={{ width: "100%" }} size="small">
                  <Input
                    placeholder="目标项"
                    value={o.title}
                    onChange={(e) => updateObjective(idx, "title", e.target.value)}
                    disabled={!canEditObjectives()}
                  />
                  <Input.TextArea
                    placeholder="目标描述"
                    rows={2}
                    value={o.description}
                    onChange={(e) => updateObjective(idx, "description", e.target.value)}
                    disabled={!canEditObjectives()}
                  />
                  <Input.TextArea
                    placeholder="衡量标准（4分及5分需写出分项考核标准）"
                    rows={2}
                    value={o.measure_criteria}
                    onChange={(e) => updateObjective(idx, "measure_criteria", e.target.value)}
                    disabled={!canEditObjectives()}
                  />
                  {canEditObjectives() && editingObjectives.length > 1 && (
                    <Button type="link" danger icon={<DeleteOutlined />} size="small" onClick={() => removeObjective(idx)}>
                      删除
                    </Button>
                  )}
                </Space>
              </div>
            ))}
            {canEditObjectives() && (
              <Space style={{ marginTop: 8 }}>
                <Button icon={<PlusOutlined />} size="small" onClick={addObjective}>
                  添加目标
                </Button>
                <Button type="primary" loading={submitting} onClick={() => saveObjectives(false)} disabled={!objectiveFormChanged}>
                  保存草稿
                </Button>
                <Button type="primary" loading={submitting} onClick={() => saveObjectives(true)}>
                  提交上级审批
                </Button>
              </Space>
            )}

            {!canEditObjectives() && plan.objectives.length > 0 && (
              <Table
                rowKey="id"
                dataSource={plan.objectives}
                size="small"
                pagination={false}
                columns={[
                  { title: "目标项", dataIndex: "title", key: "title" },
                  { title: "描述", dataIndex: "description", key: "description", ellipsis: true },
                  { title: "衡量标准", dataIndex: "measure_criteria", key: "measure_criteria", ellipsis: true },
                  { title: "状态", dataIndex: "status", key: "status", render: (v: string) => <Tag>{v}</Tag> },
                ]}
              />
            )}

            {canApproveObjectives() && (
              <Card size="small" title="目标审批" style={{ marginTop: 16 }}>
                <Space>
                  <Button type="primary" onClick={approveObjectives}>
                    批准目标
                  </Button>
                  <Button
                    danger
                    onClick={() => {
                      const reason = window.prompt("请输入驳回原因");
                      if (reason) rejectObjectives(reason);
                    }}
                  >
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
            <Input type="date" value={hrEndDate} onChange={(e) => setHrEndDate(e.target.value)} />
          </Form.Item>
          <Form.Item label="说明">
            <Input.TextArea rows={3} value={hrNote} onChange={(e) => setHrNote(e.target.value)} placeholder="如延期原因" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
