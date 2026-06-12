// 自评页 + 查看最终结果页 + 互评人邀请（根据周期状态切换）
import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { api } from "@/services/api";
import { useAuth } from "@/stores/auth";

import ValueGradeForm, { ValueGradeDisplay } from "@/components/ValueGradeForm";
const PERF_LEVEL_LABEL: Record<string, string> = {
  excellent: "优秀",
  exceed_part: "部分超出预期",
  meet: "符合预期",
  below_part: "部分不符合预期",
  below: "不符合预期",
};

interface ObjView {
  id: number;
  title: string;
  description: string;
  measure_criteria: string;
  weight: number;
  status: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  reject_reason: string | null;
}

interface Detail {
  cycle: { id: number; name: string; status: string };
  user: { id: number; name: string; position: string | null };
  participant_status: string;
  final_perf_score: number | null;
  final_perf_level: string | null;
  final_value_belief: string | null;
  final_value_team: string | null;
  final_value_growth: string | null;
  result_pending_feedback: boolean | null;
  objectives: ObjView[];
  self_evaluation: EvalView | null;
  superior_evaluation: EvalView | null;
}

interface EvalView {
  perf_score: number | null;
  perf_level: string | null;
  value_belief_grade: string | null;
  value_belief_example: string | null;
  value_team_grade: string | null;
  value_team_example: string | null;
  value_growth_grade: string | null;
  value_growth_example: string | null;
  key_results: string | null;
  comment: string | null;
  submitted_at: string | null;
}

interface PeerCandidate {
  user_id: number;
  name: string;
  position: string | null;
  status: string; // pending / approved / removed
  proposed_by: string | null;
}

interface UserBrief {
  id: number;
  name: string;
  position: string | null;
}

// ========== 绩效目标区块（可编辑 / 只读 / 审批状态）==========
interface ObjItem { title: string; description: string; measure_criteria: string; weight: number }

const STATUS_LABEL: Record<string, { text: string; color: string }> = {
  draft: { text: "草稿", color: "default" },
  pending_review: { text: "待上级审批", color: "orange" },
  approved: { text: "已确认", color: "green" },
  locked: { text: "已锁定", color: "blue" },
  // pending_adjustment 状态目前不直接体现在 objective 表上，而是通过 adjustments API 查询
};

function ObjectivesSection({
  cycleId, objectives, canEdit, onSaved
}: {
  cycleId: number;
  objectives: ObjView[];
  canEdit: boolean;
  onSaved: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [adjusting, setAdjusting] = useState(false);
  const [items, setItems] = useState<ObjItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [adjReason, setAdjReason] = useState("");
  const [adjSubmitting, setAdjSubmitting] = useState(false);

  useEffect(() => {
    if (objectives.length > 0) {
      setItems(objectives.map((o) => ({ title: o.title, description: o.description, measure_criteria: o.measure_criteria, weight: o.weight })));
    } else {
      setItems([]);
    }
  }, [objectives]);

  function addRow() {
    setItems([...items, { title: "", description: "", measure_criteria: "", weight: 0 }]);
  }
  function removeRow(idx: number) {
    setItems(items.filter((_, i) => i !== idx));
  }
  function updateRow(idx: number, field: keyof ObjItem, value: string | number) {
    const next = [...items];
    (next[idx] as any)[field] = value;
    setItems(next);
  }

  async function onSave() {
    const total = items.reduce((s, i) => s + (i.weight || 0), 0);
    if (total !== 100) { message.error(`权重总和必须为 100，当前为 ${total}`); return; }
    if (items.some((i) => !i.title.trim())) { message.error("目标标题不能为空"); return; }
    setSaving(true);
    try {
      await api.put(`/v1/cycles/${cycleId}/objectives`, { items });
      message.success("目标草稿已保存");
      setEditing(false);
      onSaved();
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "保存失败");
    } finally { setSaving(false); }
  }

  async function onSubmitForReview() {
    setSubmitting(true);
    try {
      await api.post(`/v1/cycles/${cycleId}/objectives/submit`);
      message.success("目标已提交上级审批");
      onSaved();
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "提交失败");
    } finally { setSubmitting(false); }
  }

  const overallStatus = objectives.length > 0
    ? objectives.some((o) => o.status === "pending_review")
      ? "pending_review"
      : objectives.some((o) => o.status === "draft")
        ? "draft"
        : objectives[0]?.status ?? "draft"
    : "draft";

  const hasDraft = objectives.some((o) => o.status === "draft");
  const allApproved = objectives.length > 0 && objectives.every((o) => o.status === "approved" || o.status === "locked");
  const [pendingAdj, setPendingAdj] = useState<any | null>(null);
  async function loadPendingAdjustment() {
    try {
      const r = await api.get(`/v1/cycles/${cycleId}/objectives/adjustments`);
      const pending = r.data.find((a: any) => a.status === "pending");
      setPendingAdj(pending || null);
    } catch { setPendingAdj(null); }
  }
  useEffect(() => { loadPendingAdjustment(); }, [cycleId]);
  const rejected = objectives.find((o) => o.reject_reason);

  async function onRequestAdjustment() {
    const total = items.reduce((s, i) => s + (i.weight || 0), 0);
    if (total !== 100) { message.error(`权重总和必须为 100，当前为 ${total}`); return; }
    if (items.some((i) => !i.title.trim())) { message.error("目标标题不能为空"); return; }
    if (!adjReason.trim()) { message.error("调整原因不能为空"); return; }
    setAdjSubmitting(true);
    try {
      await api.post(`/v1/cycles/${cycleId}/objectives/request-adjustment`, { items, reason: adjReason });
      message.success("调整申请已提交，等待上级审批");
      setAdjusting(false);
      setAdjReason("");
      onSaved();
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "提交失败");
    } finally { setAdjSubmitting(false); }
  }

  // 只读模式
  if (!editing && !adjusting) {
    return (
      <Card
        title={<Space>绩效目标<Tag color={STATUS_LABEL[overallStatus]?.color}>{STATUS_LABEL[overallStatus]?.text}</Tag></Space>}
        extra={canEdit && (
          <Space>
            {hasDraft && (
              <Button type="primary" onClick={onSubmitForReview} loading={submitting}>
                提交上级审批
              </Button>
            )}
            {allApproved && (
              <Button onClick={() => { setAdjusting(true); setItems(objectives.map((o) => ({ title: o.title, description: o.description, measure_criteria: o.measure_criteria, weight: o.weight }))); }}>
                申请调整
              </Button>
            )}
            {!allApproved && !pendingAdj && (
              <Button onClick={() => { setEditing(true); if (items.length === 0) addRow(); }}>
                {objectives.length > 0 ? "修改目标" : "录入目标"}
              </Button>
            )}
          </Space>
        )}
      >
        {objectives.length === 0 ? (
          <Alert type="warning" showIcon message="你还没有绩效目标，请先录入目标" />
        ) : (
          <>
            {rejected && (
              <Alert
                type="error"
                showIcon
                style={{ marginBottom: 12 }}
                message={`上级驳回原因：${rejected.reject_reason}`}
              />
            )}
            <Table rowKey="id" size="small" pagination={false} dataSource={objectives}
              columns={[
                { title: "目标", dataIndex: "title" },
                { title: "描述", dataIndex: "description", ellipsis: true },
                { title: "衡量标准", dataIndex: "measure_criteria", ellipsis: true },
                { title: "权重", dataIndex: "weight", render: (v) => `${v}%` },
                {
                  title: "状态",
                  dataIndex: "status",
                  render: (v) => {
                    const s = STATUS_LABEL[v] ?? { text: v, color: "default" };
                    return <Tag color={s.color}>{s.text}</Tag>;
                  },
                },
              ]}
            />
          </>
        )}
      </Card>
    );
  }

  // 调整申请模式
  if (adjusting) {
    const totalWeight = items.reduce((s, i) => s + (i.weight || 0), 0);
    return (
      <Card title="申请调整绩效目标" extra={<Space>
        <Tag color={totalWeight === 100 ? "green" : "red"}>权重合计 {totalWeight}%</Tag>
        <Button onClick={() => setAdjusting(false)}>取消</Button>
        <Button type="primary" onClick={onRequestAdjustment} loading={adjSubmitting}>提交调整申请</Button>
      </Space>}>
        <Space direction="vertical" style={{ width: "100%" }}>
          <Alert type="info" showIcon message="调整申请需上级审批通过后才生效" style={{ marginBottom: 8 }} />
          <Input.TextArea rows={2} placeholder="调整原因（必填）" value={adjReason} onChange={(e) => setAdjReason(e.target.value)} />
          {items.map((item, idx) => (
            <Card key={idx} size="small" type="inner" title={`目标 ${idx + 1}`}
              extra={<a onClick={() => removeRow(idx)} style={{ color: "red" }}>删除</a>}>
              <Space direction="vertical" style={{ width: "100%" }}>
                <Input placeholder="目标标题" value={item.title} onChange={(e) => updateRow(idx, "title", e.target.value)} />
                <Input.TextArea placeholder="目标描述" rows={2} value={item.description} onChange={(e) => updateRow(idx, "description", e.target.value)} />
                <Input placeholder="衡量标准（如何算达成）" value={item.measure_criteria} onChange={(e) => updateRow(idx, "measure_criteria", e.target.value)} />
                <InputNumber placeholder="权重%" min={1} max={100} value={item.weight || undefined} onChange={(v) => updateRow(idx, "weight", v ?? 0)} addonAfter="%" />
              </Space>
            </Card>
          ))}
          <Button type="dashed" block onClick={addRow}>+ 添加目标</Button>
        </Space>
      </Card>
    );
  }

  // 编辑模式
  const totalWeight = items.reduce((s, i) => s + (i.weight || 0), 0);
  return (
    <Card title="录入/修改绩效目标" extra={<Space>
      <Tag color={totalWeight === 100 ? "green" : "red"}>权重合计 {totalWeight}%</Tag>
      <Button onClick={() => setEditing(false)}>取消</Button>
      <Button type="primary" onClick={onSave} loading={saving}>保存草稿</Button>
    </Space>}>
      <Space direction="vertical" style={{ width: "100%" }}>
        {items.map((item, idx) => (
          <Card key={idx} size="small" type="inner" title={`目标 ${idx + 1}`}
            extra={<a onClick={() => removeRow(idx)} style={{ color: "red" }}>删除</a>}>
            <Space direction="vertical" style={{ width: "100%" }}>
              <Input placeholder="目标标题" value={item.title} onChange={(e) => updateRow(idx, "title", e.target.value)} />
              <Input.TextArea placeholder="目标描述" rows={2} value={item.description} onChange={(e) => updateRow(idx, "description", e.target.value)} />
              <Input placeholder="衡量标准（如何算达成）" value={item.measure_criteria} onChange={(e) => updateRow(idx, "measure_criteria", e.target.value)} />
              <InputNumber placeholder="权重%" min={1} max={100} value={item.weight || undefined} onChange={(v) => updateRow(idx, "weight", v ?? 0)} addonAfter="%" />
            </Space>
          </Card>
        ))}
        <Button type="dashed" block onClick={addRow}>+ 添加目标</Button>
      </Space>
    </Card>
  );
}

// 互评人邀请区块：最多 5 人；Leader 审核通过后不可再改
function PeerInviteSection({ cycleId, disabled }: { cycleId: number; disabled: boolean }) {
  const me = useAuth((s) => s.user)!;
  const [candidates, setCandidates] = useState<PeerCandidate[]>([]);
  const [allUsers, setAllUsers] = useState<UserBrief[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [saving, setSaving] = useState(false);

  async function load() {
    const r = await api.get<PeerCandidate[]>(`/v1/cycles/${cycleId}/peer/candidates`);
    setCandidates(r.data);
    // employee-proposed 的作为可编辑初值；leader-added 和 approved 都不展示在选择框里
    setSelected(r.data.filter((c) => c.proposed_by === "employee" && c.status !== "removed").map((c) => c.user_id));
    // 候选人：从周期参与人列表获取（排除自己、超管、HR）
    const u = await api.get<{items: any[]; total: number}>(`/v1/cycles/${cycleId}/participants?page_size=9999`);
    setAllUsers(
      u.data.items
        .filter((x) => x.user_id !== me.id)
        .filter((x) => x.role !== "super_admin" && x.role !== "hrbp")
        .map((x) => ({ id: x.user_id, name: x.user_name, position: x.user_position }))
    );
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cycleId]);

  const hasApproved = candidates.some((c) => c.status === "approved");

  async function onSubmit() {
    setSaving(true);
    try {
      await api.post(`/v1/cycles/${cycleId}/peer/invite`, { peer_user_ids: selected });
      message.success("已提交互评人名单，等待上级审核");
      await load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "提交失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="邀请互评人（最多 5 人）">
      {hasApproved ? (
        <Alert
          type="success"
          showIcon
          style={{ marginBottom: 12 }}
          message="上级已确认互评名单，不能再修改"
        />
      ) : (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="选择希望对你做 360° 评价的同事；上级会审核并可能增删"
        />
      )}

      <Space direction="vertical" style={{ width: "100%" }}>
        <Select
          mode="multiple"
          disabled={disabled || hasApproved}
          value={selected}
          onChange={(v) => setSelected(v.slice(0, 5))}
          style={{ width: "100%" }}
          placeholder="最多选 5 人"
          options={allUsers.map((u) => ({
            value: u.id,
            label: `${u.name}（${u.position ?? ""}）`,
          }))}
        />
        {!hasApproved && (
          <Button type="primary" onClick={onSubmit} loading={saving} disabled={disabled}>
            保存互评名单
          </Button>
        )}
        {candidates.length > 0 && (
          <Table
            size="small"
            pagination={false}
            rowKey="user_id"
            dataSource={candidates}
            columns={[
              { title: "姓名", dataIndex: "name" },
              { title: "职位", dataIndex: "position" },
              {
                title: "来源",
                dataIndex: "proposed_by",
                render: (v) => (v === "leader" ? <Tag color="blue">上级加</Tag> : <Tag>我选的</Tag>),
              },
              {
                title: "状态",
                dataIndex: "status",
                render: (v) =>
                  v === "approved" ? <Tag color="green">已确认</Tag> : v === "removed" ? <Tag>被移除</Tag> : <Tag color="orange">待审核</Tag>,
              },
            ]}
          />
        )}
      </Space>
    </Card>
  );
}

export default function SelfEval() {
  const { cycleId } = useParams();
  const user = useAuth((s) => s.user)!;
  const [detail, setDetail] = useState<Detail | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();

  async function reload() {
    const r = await api.get<Detail>(`/v1/cycles/${cycleId}/users/${user.id}/detail`);
    setDetail(r.data);
    if (r.data.self_evaluation) {
      form.setFieldsValue(r.data.self_evaluation);
    }
  }

  useEffect(() => {
    reload().catch(() => message.error("加载失败"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cycleId]);

  const readonly = useMemo(() => {
    // 周期不在进行中 = 不可编辑
    return detail?.cycle.status !== "in_progress";
  }, [detail]);

  async function onSubmit(values: any) {
    // 价值观甲事例校验交给后端三维度校验
    setSubmitting(true);
    try {
      await api.post(`/v1/cycles/${cycleId}/self-evaluation`, values);
      message.success("自评已提交");
      await reload();
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  if (!detail) return null;

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card
        title={detail.cycle.name}
        extra={<Tag color="blue">{detail.cycle.status}</Tag>}
      >
        <Descriptions column={2} size="small">
          <Descriptions.Item label="被考核人">{detail.user.name}</Descriptions.Item>
          <Descriptions.Item label="职位">{detail.user.position ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="进度">{detail.participant_status}</Descriptions.Item>
        </Descriptions>
      </Card>

      {detail.cycle.status === "published" && detail.final_perf_level && (
        <Alert
          type="success"
          showIcon
          message="你的最终绩效"
          description={
            <Space direction="vertical">
              <Tag color="gold">
                业绩 {PERF_LEVEL_LABEL[detail.final_perf_level]}（
                {detail.final_perf_score?.toFixed(2)} 分）
              </Tag>
              <ValueGradeDisplay data={detail} prefix="final_value" />
            </Space>
          }
        />
      )}

      <ObjectivesSection
        cycleId={Number(cycleId)}
        objectives={detail.objectives}
        canEdit={!readonly && detail.participant_status === "pending"}
        onSaved={reload}
      />

      <Card title={readonly ? "我的自评（只读）" : "填写自评"}>
        <Form
          form={form}
          layout="vertical"
          disabled={readonly}
          onFinish={onSubmit}
        >
          <Form.Item
            name="perf_score"
            label="业绩评分（1-5 分，0.25 分段）"
            rules={[{ required: true, message: "请打分" }]}
            extra="有效分数示例：3.00 / 3.25 / 3.50 / 4.00 / 4.75"
          >
            <InputNumber min={1} max={5} step={0.25} style={{ width: 200 }} />
          </Form.Item>
          <ValueGradeForm disabled={readonly} />
          <Form.Item
            name="key_results"
            label="关键成果（做成了什么）"
            rules={[{ required: true, message: "必填" }]}
          >
            <Input.TextArea rows={4} placeholder="与目标强关联的产出" />
          </Form.Item>
          <Form.Item name="comment" label="综合评语（做得好 / 待改进）">
            <Input.TextArea rows={3} />
          </Form.Item>
          {!readonly && (
            <Form.Item>
              <Button type="primary" htmlType="submit" loading={submitting}>
                {detail.self_evaluation ? "重新提交" : "提交自评"}
              </Button>
            </Form.Item>
          )}
        </Form>
      </Card>

      <PeerInviteSection cycleId={Number(cycleId)} disabled={readonly} />

      {detail.superior_evaluation && (
        <Card title="上级评估">
          <Descriptions column={2} size="small">
            <Descriptions.Item label="业绩分">
              {detail.superior_evaluation.perf_score?.toFixed(2)} (
              {PERF_LEVEL_LABEL[detail.superior_evaluation.perf_level ?? ""] ?? "-"})
            </Descriptions.Item>
            <Descriptions.Item label="价值观">
              <ValueGradeDisplay data={detail.superior_evaluation} prefix="value" />
            </Descriptions.Item>
            <Descriptions.Item label="关键成果" span={2}>
              <Typography.Paragraph>{detail.superior_evaluation.key_results}</Typography.Paragraph>
            </Descriptions.Item>
            <Descriptions.Item label="综合评语" span={2}>
              <Typography.Paragraph>{detail.superior_evaluation.comment}</Typography.Paragraph>
            </Descriptions.Item>
          </Descriptions>
        </Card>
      )}
    </Space>
  );
}
