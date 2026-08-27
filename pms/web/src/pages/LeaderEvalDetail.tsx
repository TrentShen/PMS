// Leader 端单人评估页：看员工目标 + 自评 + 互评名单审核 + 互评汇总 + 填上级评估
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  Alert,
  Avatar,
  Button,
  Card,
  Collapse,
  Descriptions,
  Empty,
  Form,
  Grid,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { api, formatError } from "@/services/api";
import type { FormProps } from "antd";
import type { AdjustmentView, HistoricalEvaluationView, HistoricalObjective } from "@/services/api.types";
import ValueGradeForm, { ValueGradeDisplay, expandValueGrades } from "@/components/ValueGradeForm";
import BottomActions from "@/components/ui/BottomActions";
import StatusTag from "@/components/ui/StatusTag";
import type { StatusType } from "@/components/ui/StatusTag";
import { PARTICIPANT_STATUS_LABEL, PARTICIPANT_STATUS_TYPE } from "@/components/ui/participantStatus";
import TableCardList from "@/components/ui/TableCardList";


interface ObjectiveView {
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
  status: string;  // draft / submitted（撤回后回退为 draft，内容保留）
}

interface HistoryPerf {
  cycle_id: number;
  cycle_name: string;
  final_perf_score: number | null;
  final_perf_level: string | null;
  final_value_belief: string | null;
  final_value_team: string | null;
  final_value_growth: string | null;
}

interface Detail {
  cycle: { id: number; name: string; status: string; enable_feedback: boolean };
  user: { id: number; name: string; position: string | null };
  participant_status: string;
  final_perf_score: number | null;
  final_perf_level: string | null;
  final_value_belief: string | null;
  final_value_team: string | null;
  final_value_growth: string | null;
  result_pending_feedback: boolean | null;
  objectives: ObjectiveView[];
  self_evaluation: EvalView | null;
  superior_evaluation: EvalView | null;
  history_perf?: HistoryPerf[];
  objective_cycle?: { id: number; name: string; start_date: string; end_date: string; status: string } | null;
}

// 待评估下属（"下一位"快捷跳转用，LeaderEval 列表字段的最小子集）
interface PendingParticipant {
  user_id: number;
  user_name: string;
  status: string;
}

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
const CYCLE_STATUS_TYPE: Record<string, StatusType> = {
  draft: "default", in_progress: "primary", published: "success", closed: "default",
};
// 目标周期状态（另一套枚举：draft/active/completed，勿与评估周期状态混用）
const OBJECTIVE_CYCLE_STATUS_LABEL: Record<string, string> = {
  draft: "制定中", active: "执行中", completed: "已结束",
};
// 参与人进度状态映射统一走共享组件 components/ui/participantStatus

// 互评名单审核已拆到独立页面 /peer-review（面板组件 components/PeerReviewPanel.tsx），本页只保留互评汇总

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
    | {
        perf_score: number | null;
        // 三维合并前的老数据只有 value_grade；新数据三维字段一致，渲染时优先新字段
        value_grade: string | null;
        value_belief_grade: string | null;
        value_team_grade: string | null;
        value_growth_grade: string | null;
        comment: string;
        created_at: string;
      }[]
    | null;
}

function PeerSummarySection({ cycleId, userId }: { cycleId: number; userId: number }) {
  const [sum, setSum] = useState<PeerSummary | null>(null);

  // 桌面表格与移动端卡片共用同一套渲染
  function peerCommentValueGrade(r: PeerSummary["comments"][number]) {
    return VALUE_LABEL[r.value_belief_grade ?? r.value_team_grade ?? r.value_growth_grade ?? ""] ?? "-";
  }

  function peerCommentText(v: string) {
    return (
      <Typography.Paragraph
        style={{ marginBottom: 0 }}
        ellipsis={{ rows: 4, expandable: true, symbol: "展开" }}
      >
        {v}
      </Typography.Paragraph>
    );
  }
  useEffect(() => {
    api
      .get<PeerSummary>(`/v1/cycles/${cycleId}/users/${userId}/peer/summary`)
      .then((r) => setSum(r.data))
      // 无互评数据时后端返回 total=0 正常渲染空态；请求失败需提示而非静默
      .catch((e) => {
        setSum(null);
        message.error(formatError(e, "加载互评汇总失败"));
      });
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
          valueStyle={{ color: "var(--color-primary)" }}
          suffix={sum.avg_perf_score ? `(${PERF_LEVEL_LABEL[perfLevel(sum.avg_perf_score)]})` : ""}
        />
        {(() => {
          // 价值观三维已合并为单项：取 belief 维度分布，老数据 belief 缺失时回退 team/growth
          const dist = sum.value_grade_dist;
          const dim = ["belief", "team", "growth"].find((d) =>
            Object.keys(dist).some((k) => k.startsWith(`${d}_`))
          );
          if (!dim) return null;
          return Object.entries(dist)
            .filter(([k]) => k.startsWith(`${dim}_`))
            .map(([k, n]) => (
              <Statistic key={k} title={`价值观 ${VALUE_LABEL[k.slice(dim.length + 1)] ?? "-"}`} value={`${n} 人`} />
            ));
        })()}
      </Space>
      {sum.rater_bias && sum.rater_bias.length > 0 && (
        <Card type="inner" size="small" title="手松手紧提示" style={{ marginBottom: 12 }}>
          <Space wrap>
            {sum.rater_bias.map((r) => (
              <StatusTag
                key={r.label}
                type={r.bias === "偏松" ? "danger" : r.bias === "偏紧" ? "warning" : "default"}
              >
                {r.label}：均分 {r.avg}（{r.bias}，共评 {r.count} 人）
              </StatusTag>
            ))}
          </Space>
        </Card>
      )}

      {sum.comments.length > 0 ? (
        <>
          {/* 桌面端：表格 */}
          <div className="pms-responsive-table">
            <Table
              size="small"
              rowKey={(_, i) => String(i)}
              pagination={false}
              dataSource={sum.comments}
              columns={[
                { title: "业绩", dataIndex: "perf_score", render: (v) => v?.toFixed(2) },
                { title: "价值观", render: (_, r) => peerCommentValueGrade(r) },
                {
                  title: "评语",
                  dataIndex: "comment",
                  render: (v: string) => peerCommentText(v),
                },
              ]}
            />
          </div>
          {/* 移动端：卡片列表 */}
          <TableCardList
            columns={[
              { title: "业绩", render: (r) => r.perf_score?.toFixed(2) },
              { title: "价值观", render: (r) => peerCommentValueGrade(r) },
              { title: "评语", render: (r) => peerCommentText(r.comment) },
            ]}
            dataSource={sum.comments}
            rowKey={(r) => `${r.perf_score}-${r.comment.slice(0, 16)}`}
          />
        </>
      ) : (
        <Empty description="还没有已提交的互评内容" />
      )}

      {sum.anonymous_feedback && sum.anonymous_feedback.length > 0 && (
        <Card
          type="inner"
          style={{ marginTop: 12 }}
          title="匿名主动评价（仅 HR / 部门 Leader 可见）"
        >
          {/* 桌面端：表格；移动端：卡片列表 */}
          <div className="pms-responsive-table">
            <Table
              size="small"
              rowKey={(_, i) => String(i)}
              pagination={false}
              dataSource={sum.anonymous_feedback}
              columns={[
                { title: "业绩", dataIndex: "perf_score", render: (v) => v?.toFixed(2) ?? "-" },
                {
                  title: "价值观",
                  render: (_, r) =>
                    VALUE_LABEL[r.value_belief_grade ?? r.value_team_grade ?? r.value_growth_grade ?? r.value_grade ?? ""] ?? "-",
                },
                {
                  title: "评语",
                  dataIndex: "comment",
                  render: (v: string) => (
                    <Typography.Paragraph
                      style={{ marginBottom: 0 }}
                      ellipsis={{ rows: 4, expandable: true, symbol: "展开" }}
                    >
                      {v}
                    </Typography.Paragraph>
                  ),
                },
              ]}
            />
          </div>
          <TableCardList
            columns={[
              { title: "业绩", render: (r) => r.perf_score?.toFixed(2) ?? "-" },
              {
                title: "价值观",
                render: (r) =>
                  VALUE_LABEL[r.value_belief_grade ?? r.value_team_grade ?? r.value_growth_grade ?? r.value_grade ?? ""] ?? "-",
              },
              {
                title: "评语",
                render: (r) => (
                  <Typography.Paragraph
                    style={{ marginBottom: 0 }}
                    ellipsis={{ rows: 4, expandable: true, symbol: "展开" }}
                  >
                    {r.comment}
                  </Typography.Paragraph>
                ),
              },
            ]}
            dataSource={sum.anonymous_feedback}
            rowKey={(r) => r.created_at}
          />
        </Card>
      )}
    </Card>
  );
}

function perfLevel(s: number): string {
  // 与后端 utils/score.py derive_perf_level 保持一致（边界值归入高等级）
  if (s > 4.5) return "excellent";
  if (s >= 4.0) return "exceed_part";
  if (s >= 3.5) return "meet";
  if (s >= 3.0) return "below_part";
  return "below";
}

// 历史绩效价值观：三维取其一（桌面表格与移动端卡片共用）
function historyValueGrade(r: HistoryPerf): string {
  return VALUE_LABEL[r.final_value_belief ?? r.final_value_team ?? r.final_value_growth ?? ""] ?? "-";
}

// ========== 历史目标（线下导入，只读快照） ==========
// 增量信息：无数据不渲染，加载失败静默（不影响主流程）
function HistoricalObjectivesSection({ userId }: { userId: number }) {
  const [objectives, setObjectives] = useState<HistoricalObjective[]>([]);

  useEffect(() => {
    api
      .get<HistoricalObjective[]>("/v1/import/historical-objectives", {
        params: { user_id: userId },
      })
      .then((r) => setObjectives(r.data))
      .catch(() => setObjectives([]));
  }, [userId]);

  if (objectives.length === 0) return null;

  // 按周期分组（保持接口返回顺序，组内按 order_num 排序）
  const groups: [string, HistoricalObjective[]][] = [];
  for (const o of objectives) {
    const group = groups.find(([name]) => name === o.cycle_name);
    if (group) {
      group[1].push(o);
    } else {
      groups.push([o.cycle_name, [o]]);
    }
  }
  for (const [, objs] of groups) {
    objs.sort((a, b) => a.order_num - b.order_num);
  }

  return (
    <Card title="历史目标（线下）" size="small">
      {groups.map(([cycleName, objs]) => (
        <div key={cycleName} style={{ marginBottom: 16 }}>
          <Typography.Title level={5} style={{ marginTop: 0 }}>{cycleName}</Typography.Title>
          {objs.map((o) => (
            <Card key={o.id} size="small" style={{ marginBottom: 8 }}>
              <Space size={8}>
                <Typography.Text strong>{o.title}</Typography.Text>
                {o.weight > 0 && <Tag>权重 {o.weight}</Tag>}
              </Space>
              {o.description && (
                <Typography.Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 4, whiteSpace: "pre-wrap" }}>
                  {o.description}
                </Typography.Paragraph>
              )}
              {o.measure_criteria && (
                <Typography.Paragraph type="secondary" style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}>
                  衡量标准：{o.measure_criteria}
                </Typography.Paragraph>
              )}
            </Card>
          ))}
        </div>
      ))}
    </Card>
  );
}

// ========== 历史考核详情（敏感数据，严格权限） ==========
// 仅 HR 与直属上级可见；后端越权返回 403 时静默不渲染；无数据不渲染
function HistoricalEvaluationsSection({ userId, isMobile }: { userId: number; isMobile: boolean }) {
  const [evals, setEvals] = useState<HistoricalEvaluationView[]>([]);

  useEffect(() => {
    api
      .get<HistoricalEvaluationView[]>(`/v1/history/users/${userId}/evaluations`)
      .then((r) => setEvals(r.data))
      .catch(() => setEvals([])); // 403（无权限）或其他失败均静默，不影响主流程
  }, [userId]);

  if (evals.length === 0) return null;

  // 得分 + 等级展示，形如 "3.75（符合预期，价值观 乙）"；字段缺失时返回 null（由调用方决定是否渲染该项）
  function scoreText(score: number | null, level: string | null, valueGrade: string | null): string | null {
    const extras: string[] = [];
    if (level) extras.push(PERF_LEVEL_LABEL[level] ?? level);
    if (valueGrade) extras.push(`价值观 ${VALUE_LABEL[valueGrade] ?? valueGrade}`);
    const suffix = extras.length > 0 ? `（${extras.join("，")}）` : "";
    if (score != null) return `${score.toFixed(2)}${suffix}`;
    return suffix || null;
  }

  return (
    <Card title="历史考核详情" size="small">
      {evals.map((ev) => (
        <Card key={ev.cycle_name} type="inner" size="small" title={ev.cycle_name} style={{ marginBottom: 12 }}>
          {ev.summary && (
            <Descriptions column={isMobile ? 1 : 3} size="small" style={{ marginBottom: 8 }}>
              {scoreText(ev.summary.self_score, ev.summary.self_level, ev.summary.self_value_grade) && (
                <Descriptions.Item label="自评">
                  {scoreText(ev.summary.self_score, ev.summary.self_level, ev.summary.self_value_grade)}
                </Descriptions.Item>
              )}
              {scoreText(ev.summary.superior_score, ev.summary.superior_level, ev.summary.superior_value_grade) && (
                <Descriptions.Item label="上级评估">
                  {scoreText(ev.summary.superior_score, ev.summary.superior_level, ev.summary.superior_value_grade)}
                </Descriptions.Item>
              )}
              {scoreText(ev.summary.peer_avg_score, ev.summary.peer_level, ev.summary.peer_value_grade) && (
                <Descriptions.Item label="互评平均">
                  {scoreText(ev.summary.peer_avg_score, ev.summary.peer_level, ev.summary.peer_value_grade)}
                </Descriptions.Item>
              )}
              {ev.summary.is_calibrated && (
                <>
                  {ev.summary.calibrated_score != null && (
                    <Descriptions.Item label="校准后得分">{ev.summary.calibrated_score.toFixed(2)}</Descriptions.Item>
                  )}
                  {ev.summary.calibrated_result && (
                    <Descriptions.Item label="校准后结果">{ev.summary.calibrated_result}</Descriptions.Item>
                  )}
                  {ev.summary.calibration_suggestion && (
                    <Descriptions.Item label="校准建议">{ev.summary.calibration_suggestion}</Descriptions.Item>
                  )}
                </>
              )}
              {ev.summary.comment && (
                <Descriptions.Item label="备注" span={isMobile ? 1 : 3}>
                  {ev.summary.comment}
                </Descriptions.Item>
              )}
            </Descriptions>
          )}
          {ev.detail && (
            <Collapse
              size="small"
              items={[
                {
                  key: "detail",
                  label: "详情（自评 / 上级评估 / 互评）",
                  children: (
                    <>
                      {(ev.detail.self_score != null ||
                        ev.detail.self_value_grade ||
                        ev.detail.self_output ||
                        ev.detail.self_comment) && (
                        <div style={{ marginBottom: 12 }}>
                          <Typography.Title level={5} style={{ marginTop: 0 }}>自评</Typography.Title>
                          <Descriptions column={isMobile ? 1 : 2} size="small">
                            {ev.detail.self_score != null && (
                              <Descriptions.Item label="得分">{ev.detail.self_score.toFixed(2)}</Descriptions.Item>
                            )}
                            {ev.detail.self_value_grade && (
                              <Descriptions.Item label="价值观等级">
                                {VALUE_LABEL[ev.detail.self_value_grade] ?? ev.detail.self_value_grade}
                              </Descriptions.Item>
                            )}
                            {ev.detail.self_output && (
                              <Descriptions.Item label="产出" span={isMobile ? 1 : 2}>
                                <span style={{ whiteSpace: "pre-wrap" }}>{ev.detail.self_output}</span>
                              </Descriptions.Item>
                            )}
                            {ev.detail.self_comment && (
                              <Descriptions.Item label="整体评价" span={isMobile ? 1 : 2}>
                                <span style={{ whiteSpace: "pre-wrap" }}>{ev.detail.self_comment}</span>
                              </Descriptions.Item>
                            )}
                          </Descriptions>
                        </div>
                      )}
                      {(ev.detail.superior_score != null ||
                        ev.detail.superior_value_grade ||
                        ev.detail.superior_comment) && (
                        <div style={{ marginBottom: 12 }}>
                          <Typography.Title level={5} style={{ marginTop: 0 }}>上级评估</Typography.Title>
                          <Descriptions column={isMobile ? 1 : 2} size="small">
                            {ev.detail.superior_score != null && (
                              <Descriptions.Item label="得分">{ev.detail.superior_score.toFixed(2)}</Descriptions.Item>
                            )}
                            {ev.detail.superior_value_grade && (
                              <Descriptions.Item label="价值观等级">
                                {VALUE_LABEL[ev.detail.superior_value_grade] ?? ev.detail.superior_value_grade}
                              </Descriptions.Item>
                            )}
                            {ev.detail.superior_comment && (
                              <Descriptions.Item label="评价汇总" span={isMobile ? 1 : 2}>
                                <span style={{ whiteSpace: "pre-wrap" }}>{ev.detail.superior_comment}</span>
                              </Descriptions.Item>
                            )}
                          </Descriptions>
                        </div>
                      )}
                      {ev.detail.peers.length > 0 && (
                        <div>
                          <Typography.Title level={5} style={{ marginTop: 0 }}>互评（评价人匿名）</Typography.Title>
                          {/* 桌面端：表格；移动端：卡片列表 */}
                          <div className="pms-responsive-table">
                            <Table
                              size="small"
                              rowKey="index"
                              pagination={false}
                              dataSource={ev.detail.peers}
                              columns={[
                                { title: "互评", dataIndex: "index", width: 64, render: (v: number) => `互评${v}` },
                                {
                                  title: "分数",
                                  dataIndex: "score",
                                  width: 80,
                                  render: (v: number | null) => (v != null ? v.toFixed(2) : "-"),
                                },
                                {
                                  title: "评语",
                                  dataIndex: "comment",
                                  render: (v: string | null) => (
                                    <span style={{ whiteSpace: "pre-wrap" }}>{v ?? "-"}</span>
                                  ),
                                },
                              ]}
                            />
                          </div>
                          <TableCardList
                            columns={[
                              { title: "互评", render: (p) => `互评${p.index}` },
                              { title: "分数", render: (p) => (p.score != null ? p.score.toFixed(2) : "-") },
                              {
                                title: "评语",
                                render: (p) => (
                                  <span style={{ whiteSpace: "pre-wrap" }}>{p.comment ?? "-"}</span>
                                ),
                              },
                            ]}
                            dataSource={ev.detail.peers}
                            rowKey={(p) => p.index}
                          />
                        </div>
                      )}
                    </>
                  ),
                },
              ]}
            />
          )}
        </Card>
      ))}
    </Card>
  );
}

// ========== 目标审批 ==========
const OBJ_STATUS_LABEL: Record<string, { text: string; type: StatusType }> = {
  draft: { text: "草稿", type: "default" },
  pending_review: { text: "待审批", type: "warning" },
  approved: { text: "已确认", type: "success" },
  locked: { text: "已锁定", type: "primary" },
};

// 桌面表格与移动端卡片共用同一套状态渲染
function objectiveStatusTag(v: string) {
  if (!v) return "-";
  const s: { text: string; type: StatusType } =
    OBJ_STATUS_LABEL[v] ?? { text: v, type: "default" };
  return <StatusTag type={s.type}>{s.text}</StatusTag>;
}

function ObjectivesReviewSection({
  objectiveCycleId,
  userId,
  objectives,
  cycleStatus,
  onChanged,
}: {
  objectiveCycleId: number | null;
  userId: number;
  objectives: ObjectiveView[];
  cycleStatus: string;
  onChanged: () => void;
}) {
  const [rejectReason, setRejectReason] = useState("");
  const [processing, setProcessing] = useState(false);
  const [adjustments, setAdjustments] = useState<AdjustmentView[]>([]);
  const [adjRejectReason, setAdjRejectReason] = useState("");
  const [adjProcessing, setAdjProcessing] = useState(false);

  const pendingCount = objectives.filter((o) => o.status === "pending_review").length;
  const canEdit = cycleStatus === "in_progress" || cycleStatus === "draft";

  async function loadAdjustments() {
    if (!objectiveCycleId) return;
    try {
      const r = await api.get<AdjustmentView[]>(`/v1/objective-cycles/${objectiveCycleId}/objectives/adjustments?user_id=${userId}`);
      setAdjustments(r.data);
    } catch (e) {
      // 无调整申请是正常情况（返回空数组）；请求失败需提示而非静默吞错
      setAdjustments([]);
      message.error(formatError(e, "加载调整申请失败"));
    }
  }
  useEffect(() => { loadAdjustments(); }, [objectiveCycleId, userId]);

  async function onApprove() {
    if (!objectiveCycleId) return;
    setProcessing(true);
    try {
      await api.post(`/v1/objective-cycles/${objectiveCycleId}/objectives/users/${userId}/approve`);
      message.success("目标已批准");
      onChanged();
    } catch (e) {
      message.error(formatError(e, "操作失败"));
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
    } catch (e) {
      message.error(formatError(e, "操作失败"));
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
    } catch (e) {
      message.error(formatError(e, "操作失败"));
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
    } catch (e) {
      message.error(formatError(e, "操作失败"));
    } finally { setAdjProcessing(false); }
  }

  return (
    <Card
      title={
        <Space>
          员工目标
          {pendingCount > 0 && <StatusTag type="danger">{pendingCount} 条待审批</StatusTag>}
        </Space>
      }
      extra={
        canEdit && pendingCount > 0 ? (
          <Space>
            <Popconfirm
              title="确认批准目标？"
              description="批准后目标进入执行状态，员工将按此目标被考核"
              okText="确认批准"
              cancelText="取消"
              onConfirm={onApprove}
            >
              <Button type="primary" loading={processing}>
                批准目标
              </Button>
            </Popconfirm>
          </Space>
        ) : null
      }
    >
      {objectives.length === 0 ? (
        <Alert type="warning" message="员工尚未填写目标" />
      ) : (
        <>
          {/* 桌面端：表格 */}
          <div className="pms-responsive-table">
            <Table
              rowKey="id"
              size="small"
              pagination={false}
              tableLayout="fixed"
              dataSource={objectives}
              columns={[
                { title: "目标", dataIndex: "title", width: "18%", render: (v: string) => <span style={{ whiteSpace: "pre-wrap" }}>{v}</span> },
                { title: "描述", dataIndex: "description", width: "32%", render: (v: string) => <span style={{ whiteSpace: "pre-wrap" }}>{v}</span> },
                { title: "衡量标准", dataIndex: "measure_criteria", width: "32%", render: (v: string) => <span style={{ whiteSpace: "pre-wrap" }}>{v}</span> },
                { title: "权重", dataIndex: "weight", width: "8%", render: (v) => `${v}%` },
                {
                  title: "状态",
                  dataIndex: "status",
                  render: (v) => objectiveStatusTag(v),
                },
              ]}
            />
          </div>
          {/* 移动端：卡片列表 */}
          <TableCardList<ObjectiveView>
            columns={[
              { title: "目标", render: (o) => o.title },
              { title: "描述", render: (o) => o.description || "-" },
              { title: "衡量标准", render: (o) => o.measure_criteria || "-" },
              { title: "权重", render: (o) => `${o.weight}%` },
              { title: "状态", render: (o) => objectiveStatusTag(o.status) },
            ]}
            dataSource={objectives}
            rowKey={(o) => o.id}
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
  const navigate = useNavigate();
  const [detail, setDetail] = useState<Detail | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // 移动端 Collapse 展开项；null 表示用户尚未操作，使用按状态的智能默认
  const [collapseActive, setCollapseActive] = useState<string[] | null>(null);
  const [form] = Form.useForm();
  // antd md 断点为 768px，与 global.css 的 767px 移动端断点一致
  const screens = Grid.useBreakpoint();
  const isMobile = !screens.md;

  // 上级评估草稿：localStorage 按周期+被评估人隔离，仅服务端无已提交内容时恢复一次
  const draftKey = `pms_leader_eval_draft_${cycleId}_${userId}`;
  const draftTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const draftRestored = useRef(false);

  async function reload() {
    const r = await api.get<Detail>(`/v1/cycles/${cycleId}/users/${userId}/detail`);
    setDetail(r.data);
    if (r.data.superior_evaluation) {
      // 服务端已有数据时以服务端为准，不恢复草稿
      form.setFieldsValue(r.data.superior_evaluation);
    } else if (!draftRestored.current) {
      draftRestored.current = true;
      // 隐私模式下 localStorage 访问可能抛 SecurityError，兜底跳过草稿恢复
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
    // 切换被评估人（含"下一位"跳转）时重置表单与草稿恢复标记
    draftRestored.current = false;
    form.resetFields();
    reload().catch((e) => message.error(formatError(e, "加载评估详情失败")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cycleId, userId]);

  // 组件卸载时清掉未触发的防抖计时器
  useEffect(() => {
    return () => {
      if (draftTimer.current) clearTimeout(draftTimer.current);
    };
  }, []);

  // 表单值变化时防抖 500ms 写入草稿
  function onValuesChange() {
    if (!detail || detail.cycle.status !== "in_progress") return;
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
    // 界面只填单项价值观，提交时展开为后端三维度字段（甲事例校验由后端 validate_value_grades 处理）

    setSubmitting(true);
    try {
      await api.post(
        `/v1/cycles/${cycleId}/users/${userId}/superior-evaluation`,
        expandValueGrades(values)
      );
      message.success("上级评估已提交");
      localStorage.removeItem(draftKey);
      await reload();
      await promptNextPending();
    } catch (e) {
      message.error(formatError(e, "提交失败"));
    } finally {
      setSubmitting(false);
    }
  }

  // 提交成功后：若还有已自评待评估的下属，提示快捷跳转到下一位
  async function promptNextPending() {
    try {
      const r = await api.get<{ items: PendingParticipant[]; total: number }>(
        `/v1/cycles/${cycleId}/participants`,
        { params: { only_subordinates: true, page_size: 9999 } }
      );
      const next = r.data.items.find(
        (p) => p.status === "self_done" && p.user_id !== Number(userId)
      );
      if (!next) return;
      Modal.confirm({
        title: "继续评估下一位？",
        content: `${next.user_name} 已提交自评，等待上级评估`,
        okText: "去评估",
        cancelText: "留在本页",
        onOk: () => navigate(`/leader/${cycleId}/users/${next.user_id}`),
      });
    } catch {
      // 列表拉取失败不影响已提交的评估结果
    }
  }

  // 校验失败（桌面/移动端都生效）：展开上级评估面板并滚动到第一个错误字段，
  // 避免移动端面板收起时"点了没反应"
  const onFinishFailed: FormProps<EvalView>["onFinishFailed"] = ({ errorFields }) => {
    setCollapseActive(["superior"]);
    const first = errorFields[0];
    if (!first) return;
    // 等面板展开渲染后再滚动
    window.setTimeout(() => form.scrollToField(first.name), 100);
  };

  // 撤回上级评估：退回草稿可改后重新提交；窗口/权限由后端强制（窗口外仅超管）
  const [withdrawing, setWithdrawing] = useState(false);
  async function onWithdraw() {
    setWithdrawing(true);
    try {
      await api.post(`/v1/cycles/${cycleId}/users/${userId}/superior-evaluation/withdraw`);
      message.success("已撤回为草稿，可修改后重新提交");
      await reload();
    } catch (e) {
      message.error(formatError(e, "撤回失败"));
    } finally {
      setWithdrawing(false);
    }
  }

  if (!detail) {
    return (
      <div style={{ textAlign: "center", padding: "var(--space-10)" }}>
        <Spin size="large" />
      </div>
    );
  }

  const selfEva = detail.self_evaluation;
  const readonly = detail.cycle.status !== "in_progress";
  const selfDone = detail.participant_status !== "pending";
  const showActions = !readonly && selfDone;

  const infoCard = (
    <Card
      title={
        <Space>
          <Avatar style={{ background: "var(--color-primary)" }}>
            {detail.user.name.charAt(0)}
          </Avatar>
          <span>
            {detail.user.name} · {detail.cycle.name}
          </span>
        </Space>
      }
    >
      <Descriptions column={isMobile ? 1 : 3} size="small">
        <Descriptions.Item label="职位">{detail.user.position ?? "-"}</Descriptions.Item>
        <Descriptions.Item label="状态">
          <StatusTag type={PARTICIPANT_STATUS_TYPE[detail.participant_status] ?? "default"}>
            {PARTICIPANT_STATUS_LABEL[detail.participant_status] ?? detail.participant_status}
          </StatusTag>
        </Descriptions.Item>
        <Descriptions.Item label="周期">
          <StatusTag type={CYCLE_STATUS_TYPE[detail.cycle.status] ?? "default"}>
            {CYCLE_STATUS_LABEL[detail.cycle.status] ?? detail.cycle.status}
          </StatusTag>
        </Descriptions.Item>
      </Descriptions>
    </Card>
  );

  const historyCard =
    detail.history_perf && detail.history_perf.length > 0 ? (
      <Card
        title="历史绩效"
        size="small"
        extra={<Link to={`/trend/${userId}`}>查看趋势</Link>}
      >
        {/* 桌面端：表格 */}
        <div className="pms-responsive-table">
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
                render: (_: unknown, r: HistoryPerf) => historyValueGrade(r),
              },
            ]}
          />
        </div>
        {/* 移动端：卡片列表 */}
        <TableCardList<HistoryPerf>
          columns={[
            { title: "周期", dataIndex: "cycle_name" },
            { title: "业绩分", render: (r) => r.final_perf_score?.toFixed(2) ?? "-" },
            { title: "等级", render: (r) => (r.final_perf_level ? PERF_LEVEL_LABEL[r.final_perf_level] ?? "-" : "-") },
            { title: "价值观", render: (r) => historyValueGrade(r) },
          ]}
          dataSource={detail.history_perf}
          rowKey={(r) => r.cycle_id}
        />
      </Card>
    ) : null;

  const objectiveCycleCard = detail.objective_cycle ? (
    <Card size="small" type="inner" title={`关联目标周期：${detail.objective_cycle.name}`}>
      <span>
        {detail.objective_cycle.start_date} ~ {detail.objective_cycle.end_date}，状态：
        <StatusTag>{OBJECTIVE_CYCLE_STATUS_LABEL[detail.objective_cycle.status] ?? detail.objective_cycle.status}</StatusTag>
      </span>
    </Card>
  ) : null;

  const objectivesSection = (
    <ObjectivesReviewSection
      objectiveCycleId={detail.objective_cycle?.id ?? null}
      userId={Number(userId)}
      objectives={detail.objectives}
      cycleStatus={detail.cycle.status}
      onChanged={reload}
    />
  );

  // 名单审核已移至独立页面 /peer-review，互评 Tab 只保留汇总 + 引导入口
  const peerReviewGuide = (
    <Alert
      type="info"
      showIcon
      message={
        <>
          互评名单确认已移至「互评名单」独立页面，
          <Link to="/peer-review">去审核名单</Link>
        </>
      }
    />
  );

  const peerSummarySection = <PeerSummarySection cycleId={Number(cycleId)} userId={Number(userId)} />;

  const historicalObjectivesSection = <HistoricalObjectivesSection userId={Number(userId)} />;

  const historicalEvaluationsSection = (
    <HistoricalEvaluationsSection userId={Number(userId)} isMobile={isMobile} />
  );

  const selfEvalCard = (
    <Card title="员工自评">
      {selfEva ? (
        <Descriptions column={isMobile ? 1 : 2} size="small">
          <Descriptions.Item label="业绩分">
            {selfEva.perf_score?.toFixed(2)} ({PERF_LEVEL_LABEL[selfEva.perf_level ?? ""] ?? "-"})
          </Descriptions.Item>
          <Descriptions.Item label="价值观">
            <ValueGradeDisplay data={selfEva} prefix="value" />
          </Descriptions.Item>
          <Descriptions.Item label="关键成果" span={isMobile ? 1 : 2}>
            <Typography.Paragraph
              ellipsis={{ rows: 4, expandable: true, symbol: "展开" }}
            >
              {selfEva.key_results}
            </Typography.Paragraph>
          </Descriptions.Item>
          <Descriptions.Item label="综合评语" span={isMobile ? 1 : 2}>
            <Typography.Paragraph
              ellipsis={{ rows: 4, expandable: true, symbol: "展开" }}
            >
              {selfEva.comment}
            </Typography.Paragraph>
          </Descriptions.Item>
        </Descriptions>
      ) : (
        <Alert type="warning" message="员工尚未提交自评" />
      )}
    </Card>
  );

  const superiorEvalCard = (
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
        onFinishFailed={onFinishFailed}
        onValuesChange={onValuesChange}
      >
        <Form.Item
          name="perf_score"
          label="业绩评分（1-5，0.25 分段）"
          rules={[{ required: true }]}
        >
          <InputNumber min={1} max={5} step={0.25} style={{ width: 200 }} inputMode="decimal" />
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
      </Form>
    </Card>
  );

  return (
    <div className={showActions ? "has-bottom-actions" : undefined}>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
          返回列表
        </Button>
      </Space>
      {isMobile ? (
        // 移动端：Collapse 分块，可同时展开多个区块（对照目标/自评/互评）
        // 智能默认：员工已自评（self_done/leader_done/...）展开上级评估，否则先看自评
        <Collapse
          activeKey={collapseActive ?? [selfDone ? "superior" : "self"]}
          onChange={(k) => setCollapseActive(Array.isArray(k) ? k : k ? [k] : [])}
          items={[
            {
              key: "info",
              label: "员工信息",
              children: (
                <Space direction="vertical" size="middle" style={{ width: "100%" }}>
                  {infoCard}
                  {historyCard}
                  {historicalObjectivesSection}
                  {historicalEvaluationsSection}
                  {objectiveCycleCard}
                </Space>
              ),
            },
            { key: "objectives", label: "目标", children: objectivesSection },
            { key: "self", label: "自评", children: selfEvalCard },
            {
              key: "peer",
              label: "互评",
              children: (
                <Space direction="vertical" size="middle" style={{ width: "100%" }}>
                  {peerReviewGuide}
                  {peerSummarySection}
                </Space>
              ),
            },
            { key: "superior", label: "上级评估", children: superiorEvalCard },
          ]}
        />
      ) : (
        // 桌面端：保持原有纵向布局
        <Space direction="vertical" size="large" style={{ width: "100%" }}>
          {infoCard}
          {historyCard}
          {historicalObjectivesSection}
          {historicalEvaluationsSection}
          {objectiveCycleCard}
          {objectivesSection}
          {peerReviewGuide}
          {peerSummarySection}
          {selfEvalCard}
          {superiorEvalCard}
        </Space>
      )}
      {showActions && (
        <BottomActions>
          {/* 反馈填写入口：周期开启反馈环节时，直达该下属的面谈记录页 */}
          {detail.cycle.enable_feedback && (
            <Button onClick={() => navigate(`/feedback/${cycleId}/${userId}`)}>
              面谈反馈
            </Button>
          )}
          {/* 已提交后允许撤回（窗口/权限由后端强制：窗口内上级可撤回，窗口外仅超管） */}
          {detail.superior_evaluation?.status === "submitted" && (
            <Popconfirm
              title="撤回上级评估？"
              description="撤回后退回草稿，可修改后重新提交；评估窗口已关闭时仅超管可撤回"
              okText="确认撤回"
              cancelText="取消"
              okButtonProps={{ danger: true }}
              onConfirm={onWithdraw}
            >
              <Button danger loading={withdrawing}>
                撤回评估
              </Button>
            </Popconfirm>
          )}
          <Popconfirm
            title="确认提交评估？"
            description="提交后将记录本次上级评估结果"
            okText="确认提交"
            cancelText="取消"
            onConfirm={() => form.submit()}
          >
            <Button type="primary" loading={submitting}>
              {detail.superior_evaluation?.status === "submitted" ? "重新提交" : "提交评估"}
            </Button>
          </Popconfirm>
        </BottomActions>
      )}
    </div>
  );
}
