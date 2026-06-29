// 首页："我的周期"卡片列表 + 根据角色显示不同入口
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Card, Empty, Space, Tag, Typography } from "antd";
import { ROLE } from "@/App";
import { hasAnyRole } from "@/components/RequireRole";
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

const PSTATUS_LABEL: Record<string, string> = {
  pending: "待自评",
  self_done: "自评已完成，等待上级评估",
  leader_done: "上级已评，等待发布",
  published: "已公布",
};

const TASK_TYPE_LABEL: Record<string, string> = {
  evaluation: "绩效评估",
  objective_setting: "目标制定",
};

const OBJ_STATUS_LABEL: Record<string, string> = {
  draft: "待填写",
  pending_review: "待上级审批",
  approved: "已确认",
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
              <Card key={`eval-${t.id}`} type="inner" size="small">
                <Space>
                  <Tag color="blue">{TASK_TYPE_LABEL[t.type]}</Tag>
                  <Typography.Text>{t.name}</Typography.Text>
                  <Tag>{PSTATUS_LABEL[t.participant_status ?? ""]}</Tag>
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
              <Card key={`obj-${t.id}`} type="inner" size="small">
                <Space>
                  <Tag color="green">{TASK_TYPE_LABEL[t.type]}</Tag>
                  <Typography.Text>{t.name}</Typography.Text>
                  <Tag>{OBJ_STATUS_LABEL[t.objective_status ?? ""]}</Tag>
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
        <Card title="我的试用期">
          <Space direction="vertical">
            <span>
              试用期：{myProbation.start_date} ~ {myProbation.end_date}
            </span>
            <span>
              状态：<Tag>{myProbation.status_text}</Tag>
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
          <Space direction="vertical" style={{ width: "100%" }}>
            {cycles.map((item) => (
              <Card
                key={item.cycle.id}
                type="inner"
                title={item.cycle.name}
                extra={<Tag color="blue">{STATUS_LABEL[item.cycle.status]}</Tag>}
              >
                <Space direction="vertical">
                  <span>
                    周期：{item.cycle.start_date} ~ {item.cycle.end_date}
                  </span>
                  <span>
                    我的状态：<Tag>{PSTATUS_LABEL[item.participant_status]}</Tag>
                  </span>
                  {item.participant_status === "published" && (
                    <span>
                      最终结果：
                      <Tag color="gold">
                        业绩 {PERF_LEVEL_LABEL[item.final_perf_level ?? ""]}（
                        {item.final_perf_score?.toFixed(2)} 分）
                      </Tag>
                      <Tag color="geekblue">
                        信念 {VALUE_LABEL[item.final_value_belief ?? ""] ?? "-"} /
                        团队 {VALUE_LABEL[item.final_value_team ?? ""] ?? "-"} /
                        成长 {VALUE_LABEL[item.final_value_growth ?? ""] ?? "-"}
                      </Tag>
                    </span>
                  )}
                  <Space wrap>
                    <Button
                      type="primary"
                      onClick={() =>
                        navigate(`/self/${item.cycle.id}`)
                      }
                      disabled={
                        item.cycle.status !== "in_progress" &&
                        item.cycle.status !== "published"
                      }
                    >
                      {item.cycle.status === "published"
                        ? "查看我的结果"
                        : item.participant_status === "pending"
                        ? "去自评"
                        : "查看我的自评"}
                    </Button>
                    {item.cycle.status === "published" && (
                      <Button onClick={() => navigate(`/feedback/${item.cycle.id}`)}>
                        查看反馈
                      </Button>
                    )}
                  </Space>
                </Space>
              </Card>
            ))}
          </Space>
        )}
      </Card>
    </Space>
  );
}
