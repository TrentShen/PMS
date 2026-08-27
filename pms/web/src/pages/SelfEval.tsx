// 自评页 + 查看最终结果页 + 互评人邀请（根据周期状态切换）
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Spin,
  Table,
  Typography,
  message,
} from "antd";
import { api, formatError } from "@/services/api";
import { useAuth } from "@/stores/auth";

import ValueGradeForm, { ValueGradeDisplay, expandValueGrades } from "@/components/ValueGradeForm";
import BottomActions from "@/components/ui/BottomActions";
import StatusTag, { type StatusType } from "@/components/ui/StatusTag";
import TableCardList, { type CardColumn } from "@/components/ui/TableCardList";

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

const PARTICIPANT_STATUS_LABEL: Record<string, string> = {
  pending: "待填写", self_done: "已自评", leader_done: "上级已评", published: "已公布", excluded: "已排除",
};

// 周期状态中文文案与语义色
const CYCLE_STATUS_LABEL: Record<string, string> = {
  draft: "草稿", in_progress: "进行中", published: "已公布", closed: "已归档",
};
const CYCLE_STATUS_TYPE: Record<string, StatusType> = {
  draft: "warning", in_progress: "primary", published: "success", closed: "default",
};

interface Detail {
  cycle: {
    id: number;
    name: string;
    status: string;
    objective_cycle_id?: number | null;
    enable_self_eval: boolean;
    enable_peer_eval: boolean;
    enable_calibration: boolean;
    enable_feedback: boolean;
  };
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
  objective_cycle?: { id: number; name: string; status: string; start_date: string; end_date: string } | null;
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

// ========== 绩效目标区块（只读；编辑在「目标制定」页）==========

const STATUS_LABEL: Record<string, { text: string; type: StatusType }> = {
  draft: { text: "草稿", type: "default" },
  pending_review: { text: "待上级审批", type: "warning" },
  approved: { text: "已确认", type: "success" },
  locked: { text: "已锁定", type: "primary" },
  // pending_adjustment 状态目前不直接体现在 objective 表上，而是通过 adjustments API 查询
};

function statusLabel(status: string): { text: string; type: StatusType } {
  return STATUS_LABEL[status] ?? { text: status, type: "default" };
}

// 移动端目标卡片列：与桌面 Table 并存，≤767px 由 CSS 自动切换
const OBJECTIVE_CARD_COLUMNS: CardColumn<ObjView>[] = [
  { title: "目标", render: (o) => o.title },
  { title: "描述", render: (o) => o.description || "-" },
  { title: "衡量标准", render: (o) => o.measure_criteria || "-" },
  { title: "权重", render: (o) => `${o.weight}%` },
  {
    title: "状态",
    render: (o) => {
      const s = statusLabel(o.status);
      return <StatusTag type={s.type}>{s.text}</StatusTag>;
    },
  },
];

// 绩效目标只读视图：目标的录入/审批/调整统一在「目标制定」页（MyObjectives）完成，
// 本页（自评）只展示，避免两套编辑逻辑漂移
function ObjectivesSection({ objectives }: { objectives: ObjView[] }) {
  const overallStatus = objectives.length > 0
    ? objectives.some((o) => o.status === "pending_review")
      ? "pending_review"
      : objectives.some((o) => o.status === "draft")
        ? "draft"
        : objectives[0]?.status ?? "draft"
    : "draft";
  const rejected = objectives.find((o) => o.reject_reason);

  return (
    <Card
      title={<Space>绩效目标<StatusTag type={statusLabel(overallStatus).type}>{statusLabel(overallStatus).text}</StatusTag></Space>}
    >
      {objectives.length === 0 ? (
        <Alert type="warning" showIcon message="你还没有绩效目标，请先到「目标制定」页录入目标" />
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
          <div className="pms-responsive-table">
            <Table rowKey="id" size="small" pagination={false} tableLayout="fixed" dataSource={objectives}
              columns={[
                { title: "目标", dataIndex: "title", width: "18%", render: (v: string) => <span style={{ whiteSpace: "pre-wrap" }}>{v}</span> },
                { title: "描述", dataIndex: "description", width: "32%", render: (v: string) => <span style={{ whiteSpace: "pre-wrap" }}>{v}</span> },
                { title: "衡量标准", dataIndex: "measure_criteria", width: "32%", render: (v: string) => <span style={{ whiteSpace: "pre-wrap" }}>{v}</span> },
                { title: "权重", dataIndex: "weight", width: "8%", render: (v) => `${v}%` },
                {
                  title: "状态",
                  dataIndex: "status",
                  render: (v) => {
                    const s = statusLabel(v);
                    return <StatusTag type={s.type}>{s.text}</StatusTag>;
                  },
                },
              ]}
            />
          </div>
          <TableCardList<ObjView>
            columns={OBJECTIVE_CARD_COLUMNS}
            dataSource={objectives}
            rowKey={(o) => o.id}
          />
        </>
      )}
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
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const r = await api.get<PeerCandidate[]>(`/v1/cycles/${cycleId}/peer/candidates`);
      setCandidates(r.data);
      // employee-proposed 的作为可编辑初值；leader-added 和 approved 都不展示在选择框里
      setSelected(r.data.filter((c) => c.proposed_by === "employee" && c.status !== "removed").map((c) => c.user_id));
      // 候选人：脱敏同事列表（/v1/cycles/:id/participants 按 scope 过滤后员工只剩自己，排除后下拉恒空）
      const u = await api.get<UserBrief[]>("/v1/users/colleagues");
      setAllUsers(u.data.filter((x) => x.id !== me.id));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load().catch((e) => message.error(formatError(e, "加载互评人信息失败")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cycleId]);

  const hasApproved = candidates.some((c) => c.status === "approved");

  // 新增直接生效；删除需二次确认（Popconfirm 无法挂在 Select 的 tag 关闭按钮上，用 Modal.confirm 与页面其他确认交互保持一致）
  function onSelectChange(v: number[]) {
    if (v.length >= selected.length) {
      setSelected(v.slice(0, 5));
      return;
    }
    const removedIds = selected.filter((id) => !v.includes(id));
    const names = removedIds
      .map((id) => allUsers.find((u) => u.id === id)?.name ?? String(id))
      .join("、");
    Modal.confirm({
      title: "确认移除互评人？",
      content: `将从互评名单中移除：${names}`,
      okText: "确认移除",
      cancelText: "取消",
      onOk: () => setSelected(v),
    });
  }

  async function onSubmit() {
    setSaving(true);
    try {
      await api.post(`/v1/cycles/${cycleId}/peer/invite`, { peer_user_ids: selected });
      message.success("已提交互评人名单，等待上级审核");
      await load();
    } catch (e) {
      message.error(formatError(e, "提交失败"));
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
          loading={loading}
          value={selected}
          onChange={onSelectChange}
          style={{ width: "100%" }}
          placeholder="最多选 5 人"
          showSearch
          optionFilterProp="label"
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
        {loading ? (
          <div style={{ textAlign: "center", padding: 24 }}>
            <Spin />
          </div>
        ) : (
          !loading && candidates.length > 0 && (
          <Table
            size="small"
            pagination={false}
            rowKey="user_id"
            scroll={{ x: 480 }}
            dataSource={candidates}
            columns={[
              { title: "姓名", dataIndex: "name" },
              { title: "职位", dataIndex: "position" },
              {
                title: "来源",
                dataIndex: "proposed_by",
                render: (v) => (v === "leader" ? <StatusTag type="primary">上级加</StatusTag> : <StatusTag>我选的</StatusTag>),
              },
              {
                title: "状态",
                dataIndex: "status",
                render: (v) =>
                  v === "approved" ? <StatusTag type="success">已确认</StatusTag> : v === "removed" ? <StatusTag>被移除</StatusTag> : <StatusTag type="warning">待审核</StatusTag>,
              },
            ]}
          />
          )
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
  const [form] = Form.useForm<EvalView>();

  // 自评草稿：localStorage 按用户+周期隔离（防共享设备跨人串号），仅服务端无已提交内容时恢复一次
  const draftKey = `self_draft_${user.id}_${cycleId}`;
  const draftTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const draftRestored = useRef(false);

  async function reload() {
    const r = await api.get<Detail>(`/v1/cycles/${cycleId}/users/${user.id}/detail`);
    setDetail(r.data);
    if (r.data.self_evaluation) {
      // 服务端已有数据时以服务端为准，不恢复草稿
      form.setFieldsValue(r.data.self_evaluation);
    } else if (!draftRestored.current) {
      draftRestored.current = true;
      // 隐私模式下 localStorage 抛 SecurityError，兜底跳过草稿恢复（同 stores/auth.ts safeGet）
      let raw: string | null = null;
      try {
        raw = localStorage.getItem(draftKey);
      } catch {
        raw = null;
      }
      if (raw) {
        try {
          form.setFieldsValue(JSON.parse(raw) as Partial<EvalView>);
          message.info("已恢复上次未提交的草稿");
        } catch {
          localStorage.removeItem(draftKey);
        }
      }
    }
  }

  useEffect(() => {
    // 切周期时先清掉旧防抖计时器，避免把新表单值写进上一周期的草稿 key
    if (draftTimer.current) clearTimeout(draftTimer.current);
    reload().catch((e) => message.error(formatError(e, "加载失败")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cycleId]);

  // 组件卸载时清掉未触发的防抖计时器
  useEffect(() => {
    return () => {
      if (draftTimer.current) clearTimeout(draftTimer.current);
    };
  }, []);

  const readonly = useMemo(() => {
    // 周期不在进行中 = 不可编辑
    return detail?.cycle.status !== "in_progress";
  }, [detail]);

  // 表单值变化时防抖 500ms 写入草稿
  function onValuesChange() {
    if (readonly) return;
    if (draftTimer.current) clearTimeout(draftTimer.current);
    draftTimer.current = setTimeout(() => {
      try {
        localStorage.setItem(draftKey, JSON.stringify(form.getFieldsValue()));
      } catch {
        // localStorage 不可用（隐私模式/超限）时静默跳过草稿
      }
    }, 500);
  }

  async function onSubmit(values: EvalView) {
    // 界面只填单项价值观，提交时展开为后端三维度字段（甲事例校验由后端三维度校验处理）
    setSubmitting(true);
    try {
      await api.post(`/v1/cycles/${cycleId}/self-evaluation`, expandValueGrades(values));
      message.success("自评已提交");
      localStorage.removeItem(draftKey);
      await reload();
    } catch (e) {
      message.error(formatError(e, "提交失败"));
    } finally {
      setSubmitting(false);
    }
  }

  if (!detail) {
    return (
      <div style={{ textAlign: "center", padding: 64 }}>
        <Spin size="large" />
      </div>
    );
  }

  // 底部固定操作栏仅在自评可编辑时展示，容器同步加 .has-bottom-actions 腾出空间
  const showBottomActions = detail.cycle.enable_self_eval && !readonly;

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }} className={showBottomActions ? "has-bottom-actions" : undefined}>
      <Card
        title={detail.cycle.name}
        extra={
          <StatusTag type={CYCLE_STATUS_TYPE[detail.cycle.status] ?? "default"}>
            {CYCLE_STATUS_LABEL[detail.cycle.status] ?? detail.cycle.status}
          </StatusTag>
        }
      >
        <Descriptions column={2} size="small">
          <Descriptions.Item label="被考核人">{detail.user.name}</Descriptions.Item>
          <Descriptions.Item label="职位">{detail.user.position ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="进度">{PARTICIPANT_STATUS_LABEL[detail.participant_status] ?? detail.participant_status}</Descriptions.Item>
        </Descriptions>
      </Card>

      {detail.cycle.status === "published" && detail.final_perf_level && (
        <Alert
          type="success"
          showIcon
          message="你的最终绩效"
          description={
            <Space direction="vertical">
              <StatusTag type="warning">
                业绩 {PERF_LEVEL_LABEL[detail.final_perf_level]}（
                {detail.final_perf_score?.toFixed(2)} 分）
              </StatusTag>
              <ValueGradeDisplay data={detail} prefix="final_value" />
            </Space>
          }
        />
      )}

      <ObjectivesSection objectives={detail.objectives} />

      {detail.cycle.enable_self_eval ? (
        <Card title={readonly ? "我的自评（只读）" : "填写自评"}>
          <Form
            form={form}
            layout="vertical"
            disabled={readonly}
            onFinish={onSubmit}
            onFinishFailed={({ errorFields }) => {
              // 校验失败时定位到第一个错误字段
              if (errorFields.length > 0) form.scrollToField(errorFields[0].name);
            }}
            onValuesChange={onValuesChange}
          >
            <Form.Item
              name="perf_score"
              label="业绩评分（1-5 分，0.25 分段）"
              rules={[{ required: true, message: "请打分" }]}
              extra="有效分数示例：3.00 / 3.25 / 3.50 / 4.00 / 4.75"
            >
              <InputNumber min={1} max={5} step={0.25} style={{ width: 200 }} inputMode="decimal" />
            </Form.Item>
            <ValueGradeForm disabled={readonly} />
            <Form.Item
              name="key_results"
              label="关键成果（做成了什么）"
              rules={[{ required: true, message: "必填" }]}
            >
              <Input.TextArea autoSize={{ minRows: 4 }} placeholder="与目标强关联的产出" />
            </Form.Item>
            <Form.Item name="comment" label="综合评语（做得好 / 待改进）">
              <Input.TextArea autoSize={{ minRows: 4 }} />
            </Form.Item>
            {!readonly && (
              <Form.Item style={{ marginBottom: 0 }}>
                <BottomActions>
                  <Button type="primary" htmlType="submit" loading={submitting}>
                    {detail.self_evaluation ? "重新提交" : "提交自评"}
                  </Button>
                </BottomActions>
              </Form.Item>
            )}
          </Form>
        </Card>
      ) : (
        <Alert type="info" showIcon message="本周期未开启自评环节" />
      )}

      {detail.cycle.enable_peer_eval && (
        <PeerInviteSection cycleId={Number(cycleId)} disabled={readonly} />
      )}

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
