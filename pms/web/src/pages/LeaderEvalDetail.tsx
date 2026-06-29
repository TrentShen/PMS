// Leader 端单人评估页：看员工目标 + 自评 + 互评名单审核 + 互评汇总 + 填上级评估
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Empty,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { api } from "@/services/api";
import ValueGradeForm, { ValueGradeDisplay } from "@/components/ValueGradeForm";

const VALUE_LABEL: Record<string, string> = { jia: "甲", yi: "乙", bing: "丙" };
const PERF_LEVEL_LABEL: Record<string, string> = {
  excellent: "优秀",
  exceed_part: "部分超出预期",
  meet: "符合预期",
  below_part: "部分不符合预期",
  below: "不符合预期",
};
const CYCLE_STATUS_LABEL: Record<string, string> = {
  draft: "草稿", in_progress: "进行中", published: "已公布", closed: "已关闭",
};
const PARTICIPANT_STATUS_LABEL: Record<string, string> = {
  pending: "待填写", self_done: "已自评", leader_done: "上级已评", published: "已公布", excluded: "已排除",
};

// ========== 互评名单审核 ==========
// 互评三态：pending（员工选的）/ approved（已发起）/ removed（Leader 删除）
interface PeerCandidate {
  user_id: number;
  name: string;
  position: string | null;
  status: string;
  proposed_by: string | null;
}

function PeerReviewSection({
  cycleId,
  userId,
  cycleStatus,
}: {
  cycleId: number;
  userId: number;
  cycleStatus: string;
}) {
  const [cands, setCands] = useState<PeerCandidate[]>([]);
  const [allUsers, setAllUsers] = useState<{ id: number; name: string; position: string | null }[]>([]);
  const [addIds, setAddIds] = useState<number[]>([]);
  const [removeIds, setRemoveIds] = useState<number[]>([]);
  const [saving, setSaving] = useState(false);

  async function load() {
    const r = await api.get<PeerCandidate[]>(`/v1/cycles/${cycleId}/users/${userId}/peer/pending`);
    setCands(r.data);
    const u = await api.get<{items: any[]; total: number}>(`/v1/cycles/${cycleId}/participants?page_size=9999`);
    setAllUsers(
      u.data.items
        .filter((x) => x.role !== "super_admin" && x.role !== "hrbp")
        .filter((x) => x.user_id !== userId)
        .map((x) => ({ id: x.user_id, name: x.user_name, position: x.user_position }))
    );
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cycleId, userId]);

  const pending = cands.filter((c) => c.status === "pending");
  const approved = cands.filter((c) => c.status === "approved");
  const removed = cands.filter((c) => c.status === "removed");
  const canEdit = cycleStatus === "in_progress" && approved.length === 0;

  async function onConfirm() {
    setSaving(true);
    try {
      const r = await api.post(
        `/v1/cycles/${cycleId}/users/${userId}/peer/approve`,
        {
          add_user_ids: addIds,
          remove_user_ids: removeIds,
        }
      );
      message.success(`已发起互评：新增 ${r.data.approved_tasks} 人，共 ${r.data.total_peers} 人`);
      setAddIds([]);
      setRemoveIds([]);
      await load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "操作失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="互评名单审核">
      {approved.length > 0 && (
        <Alert
          type="success"
          showIcon
          style={{ marginBottom: 12 }}
          message={`已发起 ${approved.length} 人的正式互评；不能再修改`}
        />
      )}
      {cands.length === 0 && approved.length === 0 && (
        <Alert type="info" showIcon message="员工尚未提交互评人邀请" style={{ marginBottom: 12 }} />
      )}

      {(pending.length > 0 || removed.length > 0 || approved.length > 0) && (
        <Table
          size="small"
          rowKey="user_id"
          pagination={false}
          dataSource={cands}
          style={{ marginBottom: 16 }}
          columns={[
            { title: "姓名", dataIndex: "name" },
            { title: "职位", dataIndex: "position" },
            {
              title: "来源",
              dataIndex: "proposed_by",
              render: (v) => (v === "leader" ? <Tag color="blue">上级加</Tag> : <Tag>员工选</Tag>),
            },
            {
              title: "状态",
              dataIndex: "status",
              render: (v) =>
                v === "approved" ? (
                  <Tag color="green">已发起互评</Tag>
                ) : v === "removed" ? (
                  <Tag>已移除</Tag>
                ) : (
                  <Tag color="orange">待审核</Tag>
                ),
            },
            {
              title: "操作",
              render: (_, r) =>
                canEdit && r.status === "pending" ? (
                  <a onClick={() => setRemoveIds((prev) => Array.from(new Set([...prev, r.user_id])))}>
                    拟移除
                  </a>
                ) : null,
            },
          ]}
        />
      )}

      {canEdit && (
        <Space direction="vertical" style={{ width: "100%" }}>
          <div>
            <Typography.Text>追加互评人：</Typography.Text>
            <Select
              mode="multiple"
              value={addIds}
              onChange={setAddIds}
              style={{ width: 360 }}
              placeholder="选同事"
              options={allUsers
                .filter((u) => !cands.find((c) => c.user_id === u.id))
                .map((u) => ({ value: u.id, label: `${u.name}（${u.position ?? ""}）` }))}
            />
          </div>
          {removeIds.length > 0 && (
            <div>
              <Typography.Text type="danger">
                将移除：{cands.filter((c) => removeIds.includes(c.user_id)).map((c) => c.name).join(", ")}
              </Typography.Text>
            </div>
          )}
          <Button type="primary" onClick={onConfirm} loading={saving}>
            确认并发起互评
          </Button>
        </Space>
      )}
    </Card>
  );
}

// ========== 互评汇总（被评人收到的） ==========
interface RaterBias {
  label: string;
  count: number;
  avg: number;
  global_avg: number;
  diff: number;
  bias: string;
}

interface PeerSummary {
  total: number;
  submitted: number;
  avg_perf_score: number | null;
  value_grade_dist: Record<string, number>;
  comments: { perf_score: number; value_belief_grade: string | null; value_team_grade: string | null; value_growth_grade: string | null; comment: string }[];
  rater_bias: RaterBias[];
  anonymous_feedback:
    | { perf_score: number | null; value_grade: string | null; comment: string; created_at: string }[]
    | null;
}

function PeerSummarySection({ cycleId, userId }: { cycleId: number; userId: number }) {
  const [sum, setSum] = useState<PeerSummary | null>(null);
  useEffect(() => {
    api
      .get<PeerSummary>(`/v1/cycles/${cycleId}/users/${userId}/peer/summary`)
      .then((r) => setSum(r.data))
      .catch(() => setSum(null));
  }, [cycleId, userId]);
  if (!sum) return null;
  if (sum.total === 0) return null;

  return (
    <Card title="互评汇总（评价人匿名）">
      <Space size="large" style={{ marginBottom: 12 }}>
        <Statistic title="已提交 / 总数" value={`${sum.submitted} / ${sum.total}`} />
        <Statistic
          title="平均业绩分"
          value={sum.avg_perf_score ?? "-"}
          valueStyle={{ color: "#1677ff" }}
          suffix={sum.avg_perf_score ? `(${PERF_LEVEL_LABEL[perfLevel(sum.avg_perf_score)]})` : ""}
        />
        {Object.entries(sum.value_grade_dist).map(([g, n]) => {
          const [dim, grade] = g.split("_");
          const DIM_LABEL: Record<string, string> = { belief: "信念", team: "团队", growth: "成长" };
          return (
            <Statistic key={g} title={`${DIM_LABEL[dim] ?? dim} ${VALUE_LABEL[grade]}`} value={`${n} 人`} />
          );
        })}
      </Space>
      {sum.rater_bias && sum.rater_bias.length > 0 && (
        <Card type="inner" size="small" title="手松手紧提示" style={{ marginBottom: 12 }}>
          <Space wrap>
            {sum.rater_bias.map((r) => (
              <Tag
                key={r.label}
                color={r.bias === "偏松" ? "red" : r.bias === "偏紧" ? "orange" : "default"}
              >
                {r.label}：均分 {r.avg}（{r.bias}，共评 {r.count} 人）
              </Tag>
            ))}
          </Space>
        </Card>
      )}

      {sum.comments.length > 0 ? (
        <Table
          size="small"
          rowKey={(_, i) => String(i)}
          pagination={false}
          dataSource={sum.comments}
          columns={[
            { title: "业绩", dataIndex: "perf_score", render: (v) => v?.toFixed(2) },
            { title: "价值观", render: (_, r) => (
              <Space>
                <span>信念 {VALUE_LABEL[r.value_belief_grade ?? ""] ?? "-"}</span>
                <span>团队 {VALUE_LABEL[r.value_team_grade ?? ""] ?? "-"}</span>
                <span>成长 {VALUE_LABEL[r.value_growth_grade ?? ""] ?? "-"}</span>
              </Space>
            ) },
            { title: "评语", dataIndex: "comment" },
          ]}
        />
      ) : (
        <Empty description="还没有已提交的互评内容" />
      )}

      {sum.anonymous_feedback && sum.anonymous_feedback.length > 0 && (
        <Card
          type="inner"
          style={{ marginTop: 12 }}
          title="匿名主动评价（仅 HR / 部门 Leader 可见）"
        >
          <Table
            size="small"
            rowKey={(_, i) => String(i)}
            pagination={false}
            dataSource={sum.anonymous_feedback}
            columns={[
              { title: "业绩", dataIndex: "perf_score", render: (v) => v?.toFixed(2) ?? "-" },
              { title: "价值观", dataIndex: "value_grade", render: (v) => (v ? VALUE_LABEL[v] : "-") },
              { title: "评语", dataIndex: "comment" },
            ]}
          />
        </Card>
      )}
    </Card>
  );
}

function perfLevel(s: number): string {
  if (s > 4.5) return "excellent";
  if (s > 4.0) return "exceed_part";
  if (s > 3.5) return "meet";
  if (s > 3.0) return "below_part";
  return "below";
}

// ========== 目标审批 ==========
const OBJ_STATUS_LABEL: Record<string, { text: string; color: string }> = {
  draft: { text: "草稿", color: "default" },
  pending_review: { text: "待审批", color: "orange" },
  approved: { text: "已确认", color: "green" },
  locked: { text: "已锁定", color: "blue" },
};

function ObjectivesReviewSection({
  objectiveCycleId,
  userId,
  objectives,
  cycleStatus,
  onChanged,
}: {
  objectiveCycleId: number | null;
  userId: number;
  objectives: any[];
  cycleStatus: string;
  onChanged: () => void;
}) {
  const [rejectReason, setRejectReason] = useState("");
  const [processing, setProcessing] = useState(false);
  const [adjustments, setAdjustments] = useState<any[]>([]);
  const [adjRejectReason, setAdjRejectReason] = useState("");
  const [adjProcessing, setAdjProcessing] = useState(false);

  const pendingCount = objectives.filter((o) => o.status === "pending_review").length;
  const canEdit = cycleStatus === "in_progress" || cycleStatus === "draft";

  async function loadAdjustments() {
    if (!objectiveCycleId) return;
    try {
      const r = await api.get(`/v1/objective-cycles/${objectiveCycleId}/objectives/adjustments?user_id=${userId}`);
      setAdjustments(r.data);
    } catch { setAdjustments([]); }
  }
  useEffect(() => { loadAdjustments(); }, [objectiveCycleId, userId]);

  async function onApprove() {
    if (!objectiveCycleId) return;
    setProcessing(true);
    try {
      await api.post(`/v1/objective-cycles/${objectiveCycleId}/objectives/users/${userId}/approve`);
      message.success("目标已批准");
      onChanged();
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "操作失败");
    } finally {
      setProcessing(false);
    }
  }

  async function onReject() {
    if (!rejectReason.trim()) {
      message.error("请填写驳回原因");
      return;
    }
    if (!objectiveCycleId) return;
    setProcessing(true);
    try {
      await api.post(`/v1/objective-cycles/${objectiveCycleId}/objectives/users/${userId}/reject`, {
        reason: rejectReason.trim(),
      });
      message.success("目标已驳回，员工可修改后重新提交");
      setRejectReason("");
      onChanged();
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "操作失败");
    } finally {
      setProcessing(false);
    }
  }

  const pendingAdjustment = adjustments.find((a) => a.status === "pending");

  async function onApproveAdjustment(revisionId: number) {
    if (!objectiveCycleId) return;
    setAdjProcessing(true);
    try {
      await api.post(`/v1/objective-cycles/${objectiveCycleId}/objectives/adjustments/${revisionId}/approve`);
      message.success("调整申请已批准");
      await loadAdjustments();
      onChanged();
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "操作失败");
    } finally { setAdjProcessing(false); }
  }

  async function onRejectAdjustment(revisionId: number) {
    if (!objectiveCycleId) return;
    if (!adjRejectReason.trim()) { message.error("请填写驳回原因"); return; }
    setAdjProcessing(true);
    try {
      await api.post(`/v1/objective-cycles/${objectiveCycleId}/objectives/adjustments/${revisionId}/reject`, { reason: adjRejectReason.trim() });
      message.success("调整申请已驳回");
      setAdjRejectReason("");
      await loadAdjustments();
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "操作失败");
    } finally { setAdjProcessing(false); }
  }

  return (
    <Card
      title={
        <Space>
          员工目标
          {pendingCount > 0 && <Tag color="red">{pendingCount} 条待审批</Tag>}
        </Space>
      }
      extra={
        canEdit && pendingCount > 0 ? (
          <Space>
            <Button type="primary" onClick={onApprove} loading={processing}>
              批准目标
            </Button>
          </Space>
        ) : null
      }
    >
      {objectives.length === 0 ? (
        <Alert type="warning" message="员工尚未填写目标" />
      ) : (
        <>
          <Table
            rowKey="id"
            size="small"
            pagination={false}
            dataSource={objectives}
            columns={[
              { title: "目标", dataIndex: "title" },
              { title: "描述", dataIndex: "description", ellipsis: true },
              { title: "衡量标准", dataIndex: "measure_criteria", ellipsis: true },
              { title: "权重", dataIndex: "weight", render: (v) => `${v}%` },
              {
                title: "状态",
                dataIndex: "status",
                render: (v) => {
                  if (!v) return "-";
                  const s = OBJ_STATUS_LABEL[v] ?? { text: v, color: "default" };
                  return <Tag color={s.color}>{s.text}</Tag>;
                },
              },
            ]}
          />
          {canEdit && pendingCount > 0 && (
            <div style={{ marginTop: 16 }}>
              <Space direction="vertical" style={{ width: "100%" }}>
                <Input.TextArea
                  rows={2}
                  placeholder="如需驳回，请填写原因（员工会收到此原因并修改后重新提交）"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                />
                <Button danger onClick={onReject} loading={processing}>
                  驳回目标
                </Button>
              </Space>
            </div>
          )}
          {objectives.some((o) => o.reject_reason) && (
            <Alert
              type="error"
              showIcon
              style={{ marginTop: 12 }}
              message={`上次驳回原因：${objectives.find((o) => o.reject_reason)?.reject_reason}`}
            />
          )}

          {/* 目标调整审批 */}
          {pendingAdjustment && (
            <Card type="inner" size="small" title="目标调整申请" style={{ marginTop: 16 }}>
              <Alert type="warning" showIcon message={`员工申请调整目标，原因：${pendingAdjustment.reason}`} style={{ marginBottom: 12 }} />
              <Typography.Text strong>调整前：</Typography.Text>
              <Table size="small" pagination={false} dataSource={pendingAdjustment.old_objectives || []} columns={[
                { title: "目标", dataIndex: "title" },
                { title: "权重", dataIndex: "weight", render: (v) => `${v}%` },
              ]} />
              <Typography.Text strong style={{ display: "block", marginTop: 12 }}>调整后：</Typography.Text>
              <Table size="small" pagination={false} dataSource={pendingAdjustment.new_objectives || []} columns={[
                { title: "目标", dataIndex: "title" },
                { title: "权重", dataIndex: "weight", render: (v) => `${v}%` },
              ]} />
              <Space direction="vertical" style={{ width: "100%", marginTop: 12 }}>
                <Input.TextArea rows={2} placeholder="如需驳回，请填写原因" value={adjRejectReason} onChange={(e) => setAdjRejectReason(e.target.value)} />
                <Space>
                  <Button type="primary" onClick={() => onApproveAdjustment(pendingAdjustment.id)} loading={adjProcessing}>批准调整</Button>
                  <Button danger onClick={() => onRejectAdjustment(pendingAdjustment.id)} loading={adjProcessing}>驳回调整</Button>
                </Space>
              </Space>
            </Card>
          )}
        </>
      )}
    </Card>
  );
}

export default function LeaderEvalDetail() {
  const { cycleId, userId } = useParams();
  const [detail, setDetail] = useState<any>(null);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();

  async function reload() {
    const r = await api.get(`/v1/cycles/${cycleId}/users/${userId}/detail`);
    setDetail(r.data);
    if (r.data.superior_evaluation) form.setFieldsValue(r.data.superior_evaluation);
  }

  useEffect(() => {
    reload().catch(() => message.error("加载失败"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cycleId, userId]);

  async function onSubmit(values: any) {
    // 价值观甲事例校验由后端 validate_value_grades 处理

    setSubmitting(true);
    try {
      await api.post(
        `/v1/cycles/${cycleId}/users/${userId}/superior-evaluation`,
        values
      );
      message.success("上级评估已提交");
      await reload();
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  if (!detail) return null;

  const selfEva = detail.self_evaluation;
  const readonly = detail.cycle.status !== "in_progress";
  const selfDone = detail.participant_status !== "pending";

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card title={`${detail.user.name} · ${detail.cycle.name}`}>
        <Descriptions column={3} size="small">
          <Descriptions.Item label="职位">{detail.user.position ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag>{PARTICIPANT_STATUS_LABEL[detail.participant_status] ?? detail.participant_status}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="周期">
            <Tag>{CYCLE_STATUS_LABEL[detail.cycle.status] ?? detail.cycle.status}</Tag>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {detail.history_perf && detail.history_perf.length > 0 && (
        <Card title="历史绩效" size="small">
          <Table
            rowKey="cycle_id"
            size="small"
            pagination={false}
            dataSource={detail.history_perf}
            columns={[
              { title: "周期", dataIndex: "cycle_name" },
              { title: "业绩分", dataIndex: "final_perf_score", render: (v) => v?.toFixed(2) ?? "-" },
              { title: "等级", dataIndex: "final_perf_level", render: (v) => PERF_LEVEL_LABEL[v] ?? "-" },
              {
                title: "价值观",
                render: (_: any, r: any) => (
                  <Space>
                    <span>信念 {VALUE_LABEL[r.final_value_belief] ?? "-"}</span>
                    <span>团队 {VALUE_LABEL[r.final_value_team] ?? "-"}</span>
                    <span>成长 {VALUE_LABEL[r.final_value_growth] ?? "-"}</span>
                  </Space>
                ),
              },
            ]}
          />
        </Card>
      )}

      {detail.objective_cycle && (
        <Card size="small" type="inner" title={`关联目标周期：${detail.objective_cycle.name}`}>
          <span>
            {detail.objective_cycle.start_date} ~ {detail.objective_cycle.end_date}，状态：
            <Tag>{detail.objective_cycle.status}</Tag>
          </span>
        </Card>
      )}

      <ObjectivesReviewSection
        objectiveCycleId={detail.objective_cycle?.id ?? null}
        userId={Number(userId)}
        objectives={detail.objectives}
        cycleStatus={detail.cycle.status}
        onChanged={reload}
      />

      <PeerReviewSection cycleId={Number(cycleId)} userId={Number(userId)} cycleStatus={detail.cycle.status} />

      <PeerSummarySection cycleId={Number(cycleId)} userId={Number(userId)} />

      <Card title="员工自评">
        {selfEva ? (
          <Descriptions column={2} size="small">
            <Descriptions.Item label="业绩分">
              {selfEva.perf_score?.toFixed(2)} ({PERF_LEVEL_LABEL[selfEva.perf_level]})
            </Descriptions.Item>
            <Descriptions.Item label="价值观">
              <ValueGradeDisplay data={selfEva} prefix="value" />
            </Descriptions.Item>
            <Descriptions.Item label="关键成果" span={2}>
              <Typography.Paragraph>{selfEva.key_results}</Typography.Paragraph>
            </Descriptions.Item>
            <Descriptions.Item label="综合评语" span={2}>
              <Typography.Paragraph>{selfEva.comment}</Typography.Paragraph>
            </Descriptions.Item>
          </Descriptions>
        ) : (
          <Alert type="warning" message="员工尚未提交自评" />
        )}
      </Card>

      <Card title={readonly ? "上级评估（只读）" : "填写上级评估"}>
        {!selfDone && !readonly && (
          <Alert
            type="info"
            showIcon
            message="员工尚未提交自评，暂无法进行上级评估"
            style={{ marginBottom: 16 }}
          />
        )}
        <Form
          form={form}
          layout="vertical"
          disabled={readonly || !selfDone}
          onFinish={onSubmit}
        >
          <Form.Item
            name="perf_score"
            label="业绩评分（1-5，0.25 分段）"
            rules={[{ required: true }]}
          >
            <InputNumber min={1} max={5} step={0.25} style={{ width: 200 }} />
          </Form.Item>
          <ValueGradeForm disabled={readonly || !selfDone} />
          <Form.Item
            name="key_results"
            label="关键成果"
            rules={[{ required: true, message: "必填" }]}
          >
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item name="comment" label="综合评语">
            <Input.TextArea rows={3} />
          </Form.Item>
          {!readonly && selfDone && (
            <Form.Item>
              <Button type="primary" htmlType="submit" loading={submitting}>
                {detail.superior_evaluation ? "重新提交" : "提交评估"}
              </Button>
            </Form.Item>
          )}
        </Form>
      </Card>
    </Space>
  );
}
