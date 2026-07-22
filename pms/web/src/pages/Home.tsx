// 首页："我的周期"卡片列表 + 根据角色显示不同入口
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Card, Empty, Space, Typography } from "antd";
import { ROLE } from "@/App";
import { hasAnyRole } from "@/components/RequireRole";
import ResponsiveShow from "@/components/ui/ResponsiveShow";
import StatusTag from "@/components/ui/StatusTag";
import type { StatusType } from "@/components/ui/StatusTag";
import TableCardList from "@/components/ui/TableCardList";
import type { CardColumn } from "@/components/ui/TableCardList";
import { api } from "@/services/api";
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
};

const TASK_TYPE_TAG_TYPE: Record<string, StatusType> = {
  evaluation: "primary",
  objective_setting: "success",
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

export default function Home() {
  const user = useAuth((s) => s.user)!;
  const navigate = useNavigate();
  const [cycles, setCycles] = useState<MyCycleItem[]>([]);
  const [myProbation, setMyProbation] = useState<ProbationPlanBrief | null>(null);
  const [tasks, setTasks] = useState<{ evaluations: TaskItem[]; objective_settings: TaskItem[] }>({
    evaluations: [],
    objective_settings: [],
  });

  useEffect(() => {
    api.get<MyCycleItem[]>("/v1/cycles/mine").then((r) => setCycles(r.data));
    api.get<ProbationPlanBrief | null>("/v1/probation/mine").then((r) => setMyProbation(r.data));
    api.get<{ evaluations: TaskItem[]; objective_settings: TaskItem[] }>("/v1/auth/me/tasks").then((r) =>
      setTasks(r.data)
    );
  }, []);

  // 统一走 ROLE 分组；避免各页面各写一套角色字符串
  const isLeader = hasAnyRole(user.role, [...ROLE.LEADER]);
  const isHr = hasAnyRole(user.role, [...ROLE.HR]);
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

  const renderFinalResult = (item: MyCycleItem): ReactNode => (
    <Space size={4} wrap>
      <StatusTag type="warning">
        业绩 {PERF_LEVEL_LABEL[item.final_perf_level ?? ""]}（
        {item.final_perf_score?.toFixed(2)} 分）
      </StatusTag>
      <StatusTag type="info">
        信念 {VALUE_LABEL[item.final_value_belief ?? ""] ?? "-"} / 团队{" "}
        {VALUE_LABEL[item.final_value_team ?? ""] ?? "-"} / 成长{" "}
        {VALUE_LABEL[item.final_value_growth ?? ""] ?? "-"}
      </StatusTag>
    </Space>
  );

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

  // 移动端周期卡片列：周期名、状态、我的状态、最终结果
  const cycleCardColumns: CardColumn<MyCycleItem>[] = [
    { title: "周期", render: (item) => item.cycle.name },
    { title: "状态", render: (item) => renderCycleStatus(item.cycle.status) },
    { title: "我的状态", render: (item) => renderParticipantStatus(item.participant_status) },
    {
      title: "最终结果",
      render: (item) => (item.participant_status === "published" ? renderFinalResult(item) : "-"),
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
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

      {(tasks.evaluations.length > 0 || tasks.objective_settings.length > 0) && (
        <Card title="我的待办任务">
          <Space direction="vertical" style={{ width: "100%" }}>
            {tasks.evaluations.map((t) => (
              <Card key={`eval-${t.id}`} type="inner" size="small" className="pms-card-hover">
                <Space>
                  <StatusTag type={TASK_TYPE_TAG_TYPE[t.type] ?? "default"}>
                    {TASK_TYPE_LABEL[t.type]}
                  </StatusTag>
                  <Typography.Text>{t.name}</Typography.Text>
                  {renderParticipantStatus(t.participant_status ?? "")}
                  <Button
                    type="primary"
                    size="small"
                    onClick={() => navigate(`/self/${t.id}`)}
                  >
                    去处理
                  </Button>
                </Space>
              </Card>
            ))}
            {tasks.objective_settings.map((t) => (
              <Card key={`obj-${t.id}`} type="inner" size="small" className="pms-card-hover">
                <Space>
                  <StatusTag type={TASK_TYPE_TAG_TYPE[t.type] ?? "default"}>
                    {TASK_TYPE_LABEL[t.type]}
                  </StatusTag>
                  <Typography.Text>{t.name}</Typography.Text>
                  <StatusTag type={OBJ_STATUS_TAG_TYPE[t.objective_status ?? ""] ?? "default"}>
                    {OBJ_STATUS_LABEL[t.objective_status ?? ""]}
                  </StatusTag>
                  <Button
                    type="primary"
                    size="small"
                    onClick={() => navigate(`/objectives/${t.id}`)}
                  >
                    去填写
                  </Button>
                </Space>
              </Card>
            ))}
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
        {cycles.length === 0 ? (
          <Empty description="暂无周期" />
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
                        周期：{item.cycle.start_date} ~ {item.cycle.end_date}
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
