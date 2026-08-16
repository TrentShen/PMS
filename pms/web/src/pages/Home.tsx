// 首页：任务驱动 —— 首屏"当前待办"hero 卡 + 全部待办列表 + 周期卡片
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Card, Empty, List, Space, Spin, Typography, message } from "antd";
import { RightOutlined } from "@ant-design/icons";
import { ROLE } from "@/App";
import { hasAnyRole } from "@/components/RequireRole";
import ResponsiveShow from "@/components/ui/ResponsiveShow";
import StatusTag from "@/components/ui/StatusTag";
import type { StatusType } from "@/components/ui/StatusTag";
import TableCardList from "@/components/ui/TableCardList";
import type { CardColumn } from "@/components/ui/TableCardList";
import { useMobile } from "@/hooks/useMobile";
import { api, formatError } from "@/services/api";
import { useAuth } from "@/stores/auth";

interface ProbationPlanBrief {
  id: number;
  user_id: number;
  status: string;
  status_text: string;
  start_date: string;
  end_date: string;
  remaining_days: number;
}

interface TaskItem {
  type: string;
  id: number;
  name: string;
  status: string;
  participant_status?: string | null;
  objective_status?: string | null;
}

// 互评待办（只取列表需要的字段，完整结构见 PeerTasks 页）
interface PeerTaskBrief {
  id: number;
  cycle_name: string;
  target_name: string;
  status: string;
}

// 首页统一待办条目：绩效评估 / 目标制定 / 互评
interface TodoItem {
  key: string;
  type: "evaluation" | "objective_setting" | "peer";
  name: string;
  statusNode: ReactNode;
  onClick: () => void;
}

interface MyCycleItem {
  cycle: {
    id: number;
    name: string;
    status: string;
    start_date: string;
    end_date: string;
  };
  role: string;
  participant_status: string;
  final_perf_level?: string | null;
  final_value_belief?: string | null;
  final_value_team?: string | null;
  final_value_growth?: string | null;
  final_perf_score?: number | null;
}

const STATUS_LABEL: Record<string, string> = {
  draft: "草稿",
  in_progress: "进行中",
  published: "已公布",
  closed: "已归档",
};

// 周期状态语义：进行中→primary、已公布/已归档→success
const STATUS_TAG_TYPE: Record<string, StatusType> = {
  draft: "default",
  in_progress: "primary",
  published: "success",
  closed: "success",
};

const PSTATUS_LABEL: Record<string, string> = {
  pending: "待自评",
  self_done: "自评已完成，等待上级评估",
  leader_done: "上级已评，等待发布",
  published: "已公布",
};

// 参与状态语义：待自评→warning、已公布→success
const PSTATUS_TAG_TYPE: Record<string, StatusType> = {
  pending: "warning",
  self_done: "info",
  leader_done: "info",
  published: "success",
};

const TASK_TYPE_LABEL: Record<string, string> = {
  evaluation: "绩效评估",
  objective_setting: "目标制定",
  peer: "互评",
};

const TASK_TYPE_TAG_TYPE: Record<string, StatusType> = {
  evaluation: "primary",
  objective_setting: "success",
  peer: "info",
};

const OBJ_STATUS_LABEL: Record<string, string> = {
  draft: "待填写",
  pending_review: "待上级审批",
  approved: "已确认",
};

const OBJ_STATUS_TAG_TYPE: Record<string, StatusType> = {
  draft: "warning",
  pending_review: "info",
  approved: "success",
};

// 试用期状态语义：进行中→primary、待评估/延期→warning、已完成→success
const PROBATION_STATUS_TAG_TYPE: Record<string, StatusType> = {
  draft: "default",
  objective_draft: "warning",
  objective_pending_review: "info",
  in_progress: "primary",
  pending_evaluation: "warning",
  completed: "success",
  extended: "warning",
};

const PERF_LEVEL_LABEL: Record<string, string> = {
  excellent: "优秀",
  exceed_part: "部分超出预期",
  meet: "符合预期",
  below_part: "部分不符合预期",
  below: "不符合预期",
};

const VALUE_LABEL: Record<string, string> = { jia: "甲", yi: "乙", bing: "丙" };

const MS_PER_DAY = 24 * 60 * 60 * 1000;

// 距周期结束的自然天数（负数表示已逾期）
function daysUntil(endDate: string): number {
  const end = new Date(`${endDate}T23:59:59`);
  return Math.ceil((end.getTime() - Date.now()) / MS_PER_DAY);
}

export default function Home() {
  const user = useAuth((s) => s.user)!;
  const navigate = useNavigate();
  const isMobile = useMobile();
  const [cycles, setCycles] = useState<MyCycleItem[]>([]);
  const [myProbation, setMyProbation] = useState<ProbationPlanBrief | null>(null);
  const [tasks, setTasks] = useState<{ evaluations: TaskItem[]; objective_settings: TaskItem[] }>({
    evaluations: [],
    objective_settings: [],
  });
  const [pendingPeerTasks, setPendingPeerTasks] = useState<PeerTaskBrief[]>([]);
  // 四个请求并发，全部结束后才置 false，避免首屏假空态
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const requests = [
      api
        .get<MyCycleItem[]>("/v1/cycles/mine")
        .then((r) => setCycles(r.data))
        .catch((e) => message.error(formatError(e, "加载我的周期失败"))),
      api
        .get<ProbationPlanBrief | null>("/v1/probation/mine")
        .then((r) => setMyProbation(r.data))
        .catch((e) => message.error(formatError(e, "加载试用期信息失败"))),
      api
        .get<{ evaluations: TaskItem[]; objective_settings: TaskItem[] }>("/v1/auth/me/tasks")
        .then((r) => setTasks(r.data))
        .catch((e) => message.error(formatError(e, "加载待办任务失败"))),
      // 互评待办与上面的请求并发，只保留待评价的任务
      api
        .get<PeerTaskBrief[]>("/v1/peer/my-tasks")
        .then((r) => setPendingPeerTasks(r.data.filter((t) => t.status === "pending")))
        .catch((e) => message.error(formatError(e, "加载互评任务失败"))),
    ];
    void Promise.allSettled(requests).then(() => setLoading(false));
  }, []);

  // 统一走 ROLE 分组；避免各页面各写一套角色字符串
  const isLeader = hasAnyRole(user.role, [...ROLE.LEADER]);
  // 与 Layout 菜单口径一致：HR 角色或 has_hr_permission 都视为 HR
  const isHr = hasAnyRole(user.role, [...ROLE.HR]) || !!user.has_hr_permission;
  const canSeeProbationMenu = isHr || isLeader || user?.has_hr_permission;

  const renderCycleStatus = (status: string): ReactNode => (
    <StatusTag type={STATUS_TAG_TYPE[status] ?? "default"}>
      {STATUS_LABEL[status] ?? status}
    </StatusTag>
  );

  const renderParticipantStatus = (status: string): ReactNode => (
    <StatusTag type={PSTATUS_TAG_TYPE[status] ?? "default"}>
      {PSTATUS_LABEL[status] ?? status}
    </StatusTag>
  );

  // 周期剩余天数：仅进行中的周期展示；≤3 天 warning，逾期 danger
  const renderRemainingDays = (item: MyCycleItem): ReactNode => {
    if (item.cycle.status !== "in_progress") return null;
    const days = daysUntil(item.cycle.end_date);
    if (days < 0) return <StatusTag type="danger">已逾期 {Math.abs(days)} 天</StatusTag>;
    if (days <= 3) return <StatusTag type="warning">剩 {days} 天</StatusTag>;
    return <StatusTag type="default">剩 {days} 天</StatusTag>;
  };

  const renderFinalResult = (item: MyCycleItem): ReactNode => {
    // 未开反馈的周期后端会把最终结果 mask 为 null（有意设计：不开反馈就不发结果），
    // 此时不渲染分数，只给中性文案
    if (item.final_perf_level == null || item.final_perf_score == null) {
      return <Typography.Text type="secondary">结果待发布</Typography.Text>;
    }
    return (
      <Space size={4} wrap>
        <StatusTag type="warning">
          业绩 {PERF_LEVEL_LABEL[item.final_perf_level] ?? item.final_perf_level}（
          {item.final_perf_score.toFixed(2)} 分）
        </StatusTag>
        <StatusTag type="info">
          价值观 {VALUE_LABEL[item.final_value_belief ?? item.final_value_team ?? item.final_value_growth ?? ""] ?? "-"}
        </StatusTag>
      </Space>
    );
  };

  // 周期操作按钮：桌面卡片与移动端卡片共用，跳转逻辑保持一致
  const renderCycleActions = (item: MyCycleItem): ReactNode => (
    <Space wrap>
      <Button
        type="primary"
        onClick={() => navigate(`/self/${item.cycle.id}`)}
        disabled={
          item.cycle.status !== "in_progress" && item.cycle.status !== "published"
        }
      >
        {item.cycle.status === "published"
          ? "查看我的结果"
          : item.participant_status === "pending"
            ? "去自评"
            : "查看我的自评"}
      </Button>
      {item.cycle.status === "published" && (
        <Button onClick={() => navigate(`/feedback/${item.cycle.id}`)}>查看反馈</Button>
      )}
    </Space>
  );

  // 全部待办：绩效评估优先，其次目标制定，最后互评
  const todos: TodoItem[] = [
    ...tasks.evaluations.map((t) => ({
      key: `eval-${t.id}`,
      type: "evaluation" as const,
      name: t.name,
      statusNode: renderParticipantStatus(t.participant_status ?? ""),
      onClick: () => navigate(`/self/${t.id}`),
    })),
    ...tasks.objective_settings.map((t) => ({
      key: `obj-${t.id}`,
      type: "objective_setting" as const,
      name: t.name,
      statusNode: (
        <StatusTag type={OBJ_STATUS_TAG_TYPE[t.objective_status ?? ""] ?? "default"}>
          {OBJ_STATUS_LABEL[t.objective_status ?? ""]}
        </StatusTag>
      ),
      onClick: () => navigate(`/objectives/${t.id}`),
    })),
    ...pendingPeerTasks.map((t) => ({
      key: `peer-${t.id}`,
      type: "peer" as const,
      name: `互评 ${t.target_name}（${t.cycle_name}）`,
      statusNode: <StatusTag type="warning">待评价</StatusTag>,
      onClick: () => navigate("/peer"),
    })),
  ];
  // hero 取最紧急的一条（数组顺序即优先级：评估 > 目标 > 互评）
  const heroTodo = todos[0] ?? null;

  // 移动端周期卡片列：周期名、状态、剩余天数、我的状态、最终结果
  const cycleCardColumns: CardColumn<MyCycleItem>[] = [
    { title: "周期", render: (item) => item.cycle.name },
    { title: "状态", render: (item) => renderCycleStatus(item.cycle.status) },
    { title: "剩余天数", render: (item) => renderRemainingDays(item) ?? "-" },
    { title: "我的状态", render: (item) => renderParticipantStatus(item.participant_status) },
    {
      title: "最终结果",
      render: (item) => (item.participant_status === "published" ? renderFinalResult(item) : "-"),
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      {/* 首屏 hero：当前最紧急待办，一键进入 */}
      <Card>
        {heroTodo ? (
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <Typography.Text type="secondary">当前待办</Typography.Text>
            <Typography.Title level={isMobile ? 4 : 3} style={{ margin: 0 }}>
              {TASK_TYPE_LABEL[heroTodo.type]} · {heroTodo.name}
            </Typography.Title>
            <Space size={4} wrap>
              <StatusTag type={TASK_TYPE_TAG_TYPE[heroTodo.type] ?? "default"}>
                {TASK_TYPE_LABEL[heroTodo.type]}
              </StatusTag>
              {heroTodo.statusNode}
            </Space>
            <Button
              type="primary"
              size="large"
              block={isMobile}
              onClick={heroTodo.onClick}
            >
              去处理
            </Button>
            {todos.length > 1 && (
              <Typography.Text type="secondary">还有 {todos.length - 1} 条待办</Typography.Text>
            )}
          </Space>
        ) : loading ? (
          <Spin />
        ) : (
          <Typography.Text type="secondary">当前没有待办事项</Typography.Text>
        )}
      </Card>

      {/* 全部待办：整行可点，行高 ≥48px */}
      {todos.length > 1 && (
        <Card title="全部待办">
          <List
            dataSource={todos}
            renderItem={(todo) => (
              <List.Item
                onClick={todo.onClick}
                style={{ cursor: "pointer", minHeight: 48, padding: "12px 8px" }}
              >
                <Space size={8} wrap style={{ flex: 1 }}>
                  <StatusTag type={TASK_TYPE_TAG_TYPE[todo.type] ?? "default"}>
                    {TASK_TYPE_LABEL[todo.type]}
                  </StatusTag>
                  <Typography.Text>{todo.name}</Typography.Text>
                  {todo.statusNode}
                </Space>
                <RightOutlined style={{ color: "var(--color-text-tertiary)" }} />
              </List.Item>
            )}
          />
        </Card>
      )}

      {/* 角色快捷入口（待办之后） */}
      {(isHr || isLeader || canSeeProbationMenu) && (
        <Card title={`你好，${user.name}`}>
          <Space wrap>
            {isHr && (
              <Button type="primary" onClick={() => navigate("/hr")}>
                HR 管理台
              </Button>
            )}
            {(isLeader || isHr) && (
              <Button onClick={() => navigate("/leader")}>下属评估</Button>
            )}
            {canSeeProbationMenu && (
              <Button onClick={() => navigate("/probation")}>试用期管理</Button>
            )}
          </Space>
        </Card>
      )}

      {myProbation && (
        <Card title="我的试用期" className="pms-card-hover">
          <Space direction="vertical">
            <span>
              试用期：{myProbation.start_date} ~ {myProbation.end_date}
            </span>
            <span>
              状态：
              <StatusTag type={PROBATION_STATUS_TAG_TYPE[myProbation.status] ?? "default"}>
                {myProbation.status_text}
              </StatusTag>
            </span>
            <span>
              剩余天数：
              {myProbation.remaining_days < 0
                ? `已逾期 ${Math.abs(myProbation.remaining_days)} 天`
                : `${myProbation.remaining_days} 天`}
            </span>
            <Button type="primary" onClick={() => navigate(`/probation/${myProbation?.user_id}`)}>
              查看详情
            </Button>
          </Space>
        </Card>
      )}

      <Card title="我参与的周期">
        {loading ? (
          <Spin />
        ) : cycles.length === 0 ? (
          <Empty description="暂无参与的绩效周期，待 HR 发起新周期后即可在这里查看" />
        ) : (
          <>
            <ResponsiveShow on="desktop">
              <Space direction="vertical" style={{ width: "100%" }}>
                {cycles.map((item) => (
                  <Card
                    key={item.cycle.id}
                    type="inner"
                    className="pms-card-hover"
                    title={item.cycle.name}
                    extra={renderCycleStatus(item.cycle.status)}
                  >
                    <Space direction="vertical">
                      <span>
                        周期：{item.cycle.start_date} ~ {item.cycle.end_date}{" "}
                        {renderRemainingDays(item)}
                      </span>
                      <span>我的状态：{renderParticipantStatus(item.participant_status)}</span>
                      {item.participant_status === "published" && (
                        <span>最终结果：{renderFinalResult(item)}</span>
                      )}
                      {renderCycleActions(item)}
                    </Space>
                  </Card>
                ))}
              </Space>
            </ResponsiveShow>
            <ResponsiveShow on="mobile">
              <TableCardList<MyCycleItem>
                columns={cycleCardColumns}
                dataSource={cycles}
                rowKey={(item) => item.cycle.id}
                renderActions={renderCycleActions}
              />
            </ResponsiveShow>
          </>
        )}
      </Card>
    </Space>
  );
}
